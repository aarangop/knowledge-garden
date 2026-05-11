# 12 — Contract

## 1. GraphStore extension: `get_note_by_title`

New abstract method on `GraphStore` (in `services/graph_store.py`):

```python
@abstractmethod
async def get_note_by_title(self, title: str) -> Note | None:
    """Return the Note whose title matches the given string (case-insensitive).

    Uses toLower() in Cypher for the comparison so the caller does not need
    to normalise the input.

    Args:
        title: The note title to search for (any casing).

    Returns:
        The matching Note, or None if no note exists with that title.
    """
    ...
```

Neo4j implementation (in `services/neo4j_store.py`):

```cypher
MATCH (n:Note)
WHERE toLower(n.title) = toLower($title)
RETURN n
LIMIT 1
```

If the query returns no rows, return `None`. If it returns a row, reconstruct the `Note` from the node properties (same reconstruction used by `get_all_notes`).

## 2. GraphStore methods reused from spec 10

Spec 12 depends on the following `GraphStore` methods that are defined and implemented by spec 10:

- `get_note_by_id(self, note_id: object) -> Note | None`
- `get_stats(self) -> dict[str, int | list[str]]` — keys: `note_count`, `chunk_count`, `similarity_edge_count`, `related_to_edge_count`, `links_to_edge_count`, `vault_names`.

This spec does **not** redeclare or stub them. If spec 12 is implemented before spec 10, the executor must surface that ordering violation rather than introducing forward declarations or `NotImplementedError` stubs (which were the source of signature drift in earlier drafts of this contract).

## 3. MCP server: `src/knowledge_garden/mcp_server.py`

### Module-level imports

```python
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from knowledge_garden.config import AppSettings, EmbeddingConfig
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.together_embedder import TogetherAIEmbedder

logger = logging.getLogger(__name__)
```

### AppState dataclass

`AppState` holds the long-lived services initialised once during lifespan startup and shared across all tool calls.

```python
@dataclass
class AppState:
    graph_store: GraphStore
    embedder: EmbeddingService
```

### Lifespan context manager

The lifespan function is an async context manager that yields the `AppState` instance directly. The MCP SDK's `FastMCP` passes it through to `ctx.request_context.lifespan_context` inside tool functions.

```python
@asynccontextmanager
async def kg_lifespan(server: FastMCP) -> AsyncIterator[AppState]:
    """Initialise Neo4j and embedder on startup; close on shutdown."""
    settings = AppSettings()  # type: ignore[call-arg]
    embedding_config = EmbeddingConfig()

    graph_store = Neo4jGraphStore(settings.neo4j, embedding_config)
    await graph_store.initialize()

    embedder: EmbeddingService
    hf = settings.hugging_face
    if hf is not None:
        embedder = HuggingFaceEmbedder(hf, embedding_config)
    else:
        embedder = TogetherAIEmbedder(settings.together_ai, embedding_config)

    try:
        yield AppState(graph_store=graph_store, embedder=embedder)
    finally:
        await embedder.close()
        await graph_store.close()
```

### FastMCP instance

```python
mcp = FastMCP("Knowledge Garden", lifespan=kg_lifespan)
```

### Context access pattern in tool functions

Inside every tool, retrieve `AppState` from the lifespan context as follows:

```python
state: AppState = ctx.request_context.lifespan_context  # type: ignore[assignment]
```

`ctx.request_context.lifespan_context` holds whatever the lifespan yielded — in this case the `AppState` instance.

`Context` is injected automatically by the MCP SDK when a parameter is annotated with the `Context` type. The parameter must be placed **after** all user-facing parameters so that MCP clients do not see it in the tool schema.

### Tool 1: `search_notes`

```python
@mcp.tool()
async def search_notes(
    query: str,
    limit: int = 10,
    threshold: float = 0.7,
    vault: str | None = None,
    ctx: Context = ...,
) -> str:
    """Search the knowledge graph for notes semantically related to a query.

    Args:
        query: The natural-language search query.
        limit: Maximum number of results to return (1–50, default 10).
        threshold: Minimum cosine similarity score for a result to be included
                   (0.0–1.0, default 0.7).
        vault: If provided, restrict results to notes from this vault name.

    Returns:
        A JSON-encoded array of objects. Each object has the fields:
            note_title (str), source_vault (str), chunk_content (str),
            heading_context (str), score (float), original_path (str).
        Returns "[]" if no results match.
    """
```

Implementation steps:

1. Extract `AppState` via `ctx.request_context.lifespan_context`.
2. Clamp `limit` to `[1, 50]` (`max(1, min(limit, 50))`).
3. Call `state.embedder.embed([query])` → take `vectors[0]`.
4. Call `state.graph_store.find_similar_chunks(embedding=vector, limit=limit, threshold=threshold)` → `list[tuple[Chunk, float]]`.
5. For each `(chunk, score)`:
   a. Look up the parent `Note` via `state.graph_store.get_note_by_id(chunk.note_id)`. If the note is `None`, skip the chunk.
   b. If `vault` is specified and `note.vault != vault`, skip.
   c. Build a result dict with the fields listed in the docstring (no `note_id`; the MCP tool surface intentionally omits internal UUIDs).
6. `return json.dumps(results)` — `"[]"` when there are no surviving results.

Rationale: the MCP tool returns plain JSON, so a Pydantic/dataclass intermediate is unnecessary. This also avoids the historical name collision between an internal `SearchResult` dataclass here and the `SearchResult` Pydantic model defined for the FastAPI surface in spec 10.

### Tool 2: `get_note`

```python
@mcp.tool()
async def get_note(
    title: str,
    ctx: Context = ...,
) -> str:
    """Retrieve the full markdown content of a note by title.

    Args:
        title: The note title to look up (case-insensitive).

    Returns:
        The full markdown content of the note if found.
        A plain-text error message beginning with "Note not found:" if no
        note matches the given title.
    """
```

Implementation steps:

1. Extract `AppState` via `ctx.request_context.lifespan_context`.
2. Call `state.graph_store.get_note_by_title(title)`.
3. If `None`, return `f"Note not found: {title!r}"`.
4. Return `note.content`.

### Tool 3: `list_vaults`

```python
@mcp.tool()
async def list_vaults(ctx: Context = ...) -> str:
    """List all ingested vaults and their note counts.

    Returns:
        A JSON-encoded array of objects, each with fields:
            vault (str): vault name.
            note_count (int): number of notes from that vault.
        Returns "[]" if no notes have been ingested.
    """
```

Implementation steps:

1. Extract `AppState` via `ctx.request_context.lifespan_context`.
2. Call `state.graph_store.get_all_notes()` → `list[Note]`.
3. Aggregate note count per vault name using a `dict[str, int]`.
4. Serialise to `list[{"vault": str, "note_count": int}]` and return as JSON string.

### Tool 4: `get_graph_stats`

```python
@mcp.tool()
async def get_graph_stats(ctx: Context = ...) -> str:
    """Get high-level statistics about the knowledge graph.

    Returns:
        A JSON-encoded object with fields:
            note_count (int): total Note nodes.
            chunk_count (int): total Chunk nodes.
            similarity_edge_count (int): total SIMILAR_TO edges.
            related_to_edge_count (int): total RELATED_TO edges.
            links_to_edge_count (int): total LINKS_TO edges.
            vault_names (list[str]): distinct vault names.
    """
```

Implementation steps:

1. Extract `AppState` via `ctx.request_context.lifespan_context`.
2. Call `state.graph_store.get_stats()` → `dict[str, int | list[str]]` (shape defined in spec 10).
3. Return `json.dumps(stats)`. The dict already has all six expected keys; no field renaming is required.

### Entry point

```python
def main() -> None:
    """Entry point for the kg-mcp script."""
    mcp.run()
```

`mcp.run()` with no arguments uses the `stdio` transport (the default for MCP servers started by clients such as Claude Desktop). No transport argument is required for standard Claude Desktop integration.

## 4. Configuration additions

No new fields are added to `AppSettings` or `BusinessConfig`. The MCP server reads the same environment variables as the FastAPI server:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TOGETHER_API_KEY` | Yes (unless `HF_API_TOKEN` set) | — | Together AI API key |
| `NEO4J_URI` | No | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | No | `knowledge-garden` | Neo4j password |
| `NEO4J_DATABASE` | No | `neo4j` | Neo4j database name |
| `HF_API_TOKEN` | No | — | If set, use HuggingFace embedder instead of Together AI |

## 5. `pyproject.toml` changes

### New runtime dependency

Add to the `dependencies` list:

```toml
"mcp[cli]>=1.0.0",
```

### New script entry point

Add to `[project.scripts]`:

```toml
kg-mcp = "knowledge_garden.mcp_server:main"
```

Full updated `[project.scripts]` section:

```toml
[project.scripts]
kg = "knowledge_garden.cli:app"
kg-mcp = "knowledge_garden.mcp_server:main"
```

## 6. Claude Desktop integration

Add the following block to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "knowledge-garden": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/knowledge_garden", "kg-mcp"],
      "env": {
        "TOGETHER_API_KEY": "your-key-here",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_PASSWORD": "knowledge-garden"
      }
    }
  }
}
```

Replace `/path/to/knowledge_garden` with the absolute path to the repository root. Replace `your-key-here` with a valid Together AI API key. If using HuggingFace embedder instead, replace `TOGETHER_API_KEY` with `HF_API_TOKEN` and any value for `TOGETHER_API_KEY` (AppSettings requires it even when HF is used — this is a known limitation from spec 04).

## 7. Test specifications

### Unit tests — `tests/test_mcp_server.py`

All tests are marked `pytest.mark.unit`. Tests call the tool functions directly (not via MCP protocol) by injecting a mock `Context` whose `request_context.lifespan_context` attribute is the `AppState` instance — the same shape the FastMCP runtime would expose at request time.

**Fixtures needed:**

- `mock_graph_store` — `AsyncMock(spec=GraphStore)` pre-configured with sensible return values.
- `mock_embedder` — `AsyncMock(spec=EmbeddingService)` where `embed` returns `[[0.1] * 768]`.
- `mock_state` — an `AppState(graph_store=mock_graph_store, embedder=mock_embedder)` instance.
- `mock_ctx` — a `MagicMock` whose `mock_ctx.request_context.lifespan_context` attribute is set to `mock_state` directly (not wrapped in a dict). This matches the implementation, which reads `ctx.request_context.lifespan_context` and treats it as `AppState`.

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_search_notes_returns_json_string` | `query="ML concepts"`, `find_similar_chunks` returns one `(Chunk, 0.85)` pair, `get_note_by_id` returns a matching `Note` | return value is a valid JSON string; parsed array has 1 element with `note_title`, `source_vault`, `chunk_content`, `heading_context`, `score`, `original_path` keys |
| `test_search_notes_empty_results` | `find_similar_chunks` returns `[]` | return value is `"[]"` |
| `test_search_notes_vault_filter` | `vault="vault_a"`, two chunks returned where one has a note from `"vault_a"` and one from `"vault_b"` | returned JSON array has exactly 1 element from `"vault_a"` |
| `test_search_notes_limit_passed_to_store` | `limit=5` | `find_similar_chunks` called with `limit=5` |
| `test_search_notes_limit_clamped_max` | `limit=200` | `find_similar_chunks` called with `limit=50` |
| `test_search_notes_limit_clamped_min` | `limit=0` | `find_similar_chunks` called with `limit=1` |
| `test_search_notes_threshold_passed_to_store` | `threshold=0.9` | `find_similar_chunks` called with `threshold=0.9` |
| `test_search_notes_skips_note_not_found` | `get_note_by_id` returns `None` for the chunk's note | result is `"[]"` (chunk skipped) |
| `test_get_note_found` | `get_note_by_title` returns a `Note` with `content="Hello world"` | return value is `"Hello world"` |
| `test_get_note_not_found` | `get_note_by_title` returns `None` | return value starts with `"Note not found:"` |
| `test_list_vaults_returns_json` | `get_all_notes` returns 3 notes: 2 from `"v1"`, 1 from `"v2"` | parsed JSON array has 2 elements; `{"vault": "v1", "note_count": 2}` and `{"vault": "v2", "note_count": 1}` both present |
| `test_list_vaults_empty_graph` | `get_all_notes` returns `[]` | return value is `"[]"` |
| `test_get_graph_stats_returns_json` | `get_stats` returns `{"note_count": 5, "chunk_count": 20, "similarity_edge_count": 15, "related_to_edge_count": 3, "links_to_edge_count": 7, "vault_names": ["v1"]}` | return value is valid JSON; parsed dict has all six keys with correct values |

### Unit tests — `tests/test_graph_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_get_note_by_title_found` | mock session returns one Note node row with `title="My Note"` | returns a `Note` with `title="My Note"` |
| `test_get_note_by_title_case_insensitive` | stored title is `"My Note"`, query is `"my note"` | returns the same `Note` (Cypher `toLower` handles case folding) |
| `test_get_note_by_title_not_found` | mock session returns no rows | returns `None` |
| `test_get_note_by_title_returns_first_match` | mock session returns two rows | returns the first row only (LIMIT 1 in Cypher) |

## 8. Edge cases

- `search_notes` with no notes ingested yet — `find_similar_chunks` returns `[]`; tool returns `"[]"`.
- `get_note` with an empty title string — `get_note_by_title("")` returns `None`; tool returns an error message.
- `list_vaults` before any ingestion — `get_all_notes` returns `[]`; tool returns `"[]"`.
- `get_graph_stats` when `get_stats` raises an exception — the exception propagates to the MCP framework (no special handling; the client receives an MCP error response).
- Embedder failure in `search_notes` — exception propagates to MCP framework.
- `AppSettings` missing `TOGETHER_API_KEY` at server startup — `pydantic.ValidationError` raised in lifespan before the server accepts connections; the process exits with a non-zero code.

## 9. Dependencies and assumptions

- `GraphStore.find_similar_chunks` is implemented and tested (spec 05/06).
- `GraphStore.get_all_notes` is implemented and tested (spec 01).
- `Neo4jGraphStore` constructor accepts `Neo4jConfig` and `EmbeddingConfig` (confirmed from `main.py`).
- `EmbeddingService.close()` is implemented for both `TogetherAIEmbedder` and `HuggingFaceEmbedder`.
- `GraphStore.get_note_by_id(note_id: object) -> Note | None` and `GraphStore.get_stats() -> dict[str, int | list[str]]` are defined and implemented by spec 10. Spec 12 reuses these methods unchanged. The `get_stats` return dict carries the six keys specified in spec 10 (`note_count`, `chunk_count`, `similarity_edge_count`, `related_to_edge_count`, `links_to_edge_count`, `vault_names`).
- The `mcp[cli]` package (PyPI: `mcp`, version `>=1.0.0`) provides `mcp.server.fastmcp.FastMCP` and `mcp.server.fastmcp.Context`.
- `Context` is injected automatically by the MCP SDK into any tool parameter annotated with the `Context` type.
- The lifespan context is accessed in tools via `ctx.request_context.lifespan_context`, which holds the `AppState` instance yielded by `kg_lifespan`.
- `mcp.run()` with no arguments uses stdio transport, which is correct for Claude Desktop integration.
