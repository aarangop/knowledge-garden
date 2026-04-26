# Contract: CLI and Pipeline Extraction

Builds on: `specifications/01_foundation/contract.md`, `specifications/02_ingestion/contract.md`

Uses `Note`, `Chunk` from `src/knowledge_garden/models/note.py` (spec 01).
Uses `GraphStore` ABC from `src/knowledge_garden/services/graph_store.py` (spec 01).
Uses `EmbeddingService` ABC from `src/knowledge_garden/services/embedder.py` (spec 01).
Uses `VaultConfig`, `ChunkingConfig`, `Config` from `src/knowledge_garden/config.py` (specs 01, 02).
Uses `MarkdownParser` from `src/knowledge_garden/services/parser.py` (spec 02).
Uses `NoteChunker` from `src/knowledge_garden/services/chunker.py` (spec 02).

---

## 1. Dependency Additions

### 1.1 pyproject.toml Changes

Add to `[project] dependencies`:

```toml
"typer>=0.12.0",
"rich>=13.0.0",
```

Add a new table after `[project]`:

```toml
[project.scripts]
kg = "knowledge_garden.cli:app"
```

No other changes to `pyproject.toml`. The `dev` dependency groups are unchanged.

### 1.2 Dependency Tests

No automated tests are specified for dependency installation. Manual verification is sufficient (see roadmap Step 1 and Step 5).

---

## 2. IngestPipeline Service

### 2.1 Data Model

File: `src/knowledge_garden/services/pipeline.py`

```python
from dataclasses import dataclass

@dataclass
class IngestResult:
    """Summary returned by IngestPipeline.run()."""
    notes_parsed: int       # number of Note objects produced by the parser
    chunks_created: int     # total Chunk objects after chunking (before min-size filter the chunker discards)
    duration_seconds: float # wall-clock seconds for the full pipeline (monotonic)
```

`IngestResult` is a plain `dataclass`, not a Pydantic model. It carries output data only; it has no validation logic.

### 2.2 IngestPipeline Interface

File: `src/knowledge_garden/services/pipeline.py`

```python
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from knowledge_garden.config import VaultConfig
from knowledge_garden.services.chunker import NoteChunker
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.parser import MarkdownParser


ProgressCallback = Callable[[int, int, str], None]
# Called as: callback(current_index, total, note_title)
# current_index is 1-based (first note is 1, last is total)
# total is the number of notes to process
# note_title is the Note.title of the note just about to be processed


class IngestPipeline:
    """Orchestrates the full vault ingest: parse → chunk → embed → upsert.

    Dependencies are injected at construction time. The pipeline itself is
    stateless between calls to run(); calling run() twice on two different
    vaults is safe.
    """

    def __init__(
        self,
        parser: MarkdownParser,
        chunker: NoteChunker,
        embedder: EmbeddingService,
        graph_store: GraphStore,
    ) -> None:
        """
        Parameters
        ----------
        parser:
            MarkdownParser instance used to walk the vault directory.
        chunker:
            NoteChunker instance used to split each Note into Chunks.
        embedder:
            EmbeddingService implementation used to embed chunk content.
        graph_store:
            GraphStore implementation used to upsert Notes and Chunks.
        """
        ...

    async def run(
        self,
        vault_config: VaultConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestResult:
        """Run the ingest pipeline for one vault.

        Pipeline order:
        1. parser.parse_vault(vault_config) → list[Note]
        2. For each note (in order):
           a. If progress_callback is not None, call it with
              (current_index, total, note.title) before processing.
              current_index is 1-based.
           b. chunker.chunk_note(note) → list[Chunk]
           c. Accumulate chunks into a flat list.
        3. If any chunks were produced:
           a. Extract content strings from all chunks.
           b. Call await embedder.embed(texts) once for all chunks.
           c. Assign each returned vector to the corresponding chunk's
              embedding field (zip with strict=True).
        4. For each note: await graph_store.upsert_note(note).
        5. For each chunk: await graph_store.upsert_chunk(chunk).
        6. Return IngestResult(
               notes_parsed=len(notes),
               chunks_created=len(all_chunks),
               duration_seconds=<monotonic elapsed>,
           ).

        If parse_vault returns [], the embed call is skipped, upsert loops
        do not execute, and IngestResult has notes_parsed=0, chunks_created=0.

        Parameters
        ----------
        vault_config:
            VaultConfig identifying the vault to ingest.
        progress_callback:
            Optional callable invoked once per note before that note is
            chunked. Signature: (current_index: int, total: int,
            note_title: str) -> None. If None, no progress is reported.

        Returns
        -------
        IngestResult
            Summary of the completed pipeline.
        """
        ...
```

### 2.3 IngestPipeline Test Specifications

File: `tests/test_pipeline.py`

All tests are `@pytest.mark.unit`.

**Fixtures needed:**

```python
# In tests/test_pipeline.py (local) or tests/conftest.py

@pytest.fixture
def mock_parser():
    """MarkdownParser whose parse_vault is controlled per test."""
    from unittest.mock import MagicMock
    from knowledge_garden.services.parser import MarkdownParser
    return MagicMock(spec=MarkdownParser)

@pytest.fixture
def mock_chunker():
    """NoteChunker whose chunk_note is controlled per test."""
    from unittest.mock import MagicMock
    from knowledge_garden.services.chunker import NoteChunker
    return MagicMock(spec=NoteChunker)

@pytest.fixture
def sample_vault_config_obj():
    """A VaultConfig with a fixed name and path (does not need to exist on disk)."""
    from knowledge_garden.config import VaultConfig
    return VaultConfig(name="test_vault", path="/tmp/test_vault")

@pytest.fixture
def pipeline(mock_parser, mock_chunker, mock_embedder, mock_graph_store):
    """IngestPipeline with all dependencies mocked."""
    from knowledge_garden.services.pipeline import IngestPipeline
    return IngestPipeline(
        parser=mock_parser,
        chunker=mock_chunker,
        embedder=mock_embedder,
        graph_store=mock_graph_store,
    )
```

The `mock_embedder` and `mock_graph_store` fixtures come from `tests/conftest.py` (spec 01).

**Test helper — `make_note(title)`:**

```python
def make_note(title: str = "Note A"):
    from knowledge_garden.models.note import Note
    return Note(title=title, content="Some content.", vault="test_vault", original_path=f"{title}.md")
```

**Test helper — `make_chunk(note)`:**

```python
def make_chunk(note, index: int = 0):
    from knowledge_garden.models.note import Chunk
    return Chunk(note_id=note.id, content="Chunk content.", index=index)
```

#### Test cases

| Test function | Setup | Expected outcome |
|---|---|---|
| `test_pipeline_empty_vault` | `mock_parser.parse_vault` returns `[]` | `result.notes_parsed == 0`; `result.chunks_created == 0`; `mock_embedder.embed` NOT called; `mock_graph_store.upsert_note` NOT called |
| `test_pipeline_single_note_no_chunks` | `parse_vault` returns 1 Note; `chunk_note` returns `[]` | `result.notes_parsed == 1`; `result.chunks_created == 0`; `embed` NOT called; `upsert_note` called once; `upsert_chunk` NOT called |
| `test_pipeline_single_note_with_chunks` | `parse_vault` returns 1 Note; `chunk_note` returns 2 Chunks; `embed` returns 2 vectors | `result.notes_parsed == 1`; `result.chunks_created == 2`; `embed` called once with 2 texts; `upsert_note` called once; `upsert_chunk` called twice |
| `test_pipeline_multiple_notes` | `parse_vault` returns 3 Notes; `chunk_note` returns 1 Chunk each; `embed` returns 3 vectors | `result.notes_parsed == 3`; `result.chunks_created == 3`; `upsert_note` called 3 times; `upsert_chunk` called 3 times |
| `test_pipeline_embed_called_once_for_all_chunks` | `parse_vault` returns 2 Notes; each produces 3 Chunks | `embed` called exactly once; the single call receives a list of 6 texts |
| `test_pipeline_embeddings_assigned_to_chunks` | `parse_vault` returns 1 Note; `chunk_note` returns 2 Chunks; `embed` returns `[[0.1]*768, [0.2]*768]` | After `run()`, the chunks passed to `upsert_chunk` have `embedding == [0.1]*768` and `embedding == [0.2]*768` respectively |
| `test_pipeline_progress_callback_not_called_for_empty_vault` | `parse_vault` returns `[]`; `progress_callback` is a `MagicMock` | `progress_callback` is never called |
| `test_pipeline_progress_callback_called_once_per_note` | `parse_vault` returns 3 Notes; each produces 1 Chunk; callback is a `MagicMock` | `progress_callback` called exactly 3 times |
| `test_pipeline_progress_callback_receives_correct_args` | `parse_vault` returns 2 Notes with titles `"A"` and `"B"`; callback is a `MagicMock` | First call args: `(1, 2, "A")`; second call args: `(2, 2, "B")` |
| `test_pipeline_progress_callback_is_optional` | `run()` called without providing `progress_callback` | No exception; pipeline completes normally |
| `test_pipeline_result_duration_non_negative` | Any 1-note, 1-chunk setup | `result.duration_seconds >= 0` |
| `test_pipeline_result_is_ingest_result` | Any successful `run()` | Return value is an instance of `IngestResult` |
| `test_pipeline_upsert_note_called_before_upsert_chunk` | 1 Note, 1 Chunk | `upsert_note` is called before any `upsert_chunk` call (verify via `call_args_list` ordering on a combined mock) |

---

## 3. API Changes — Remove Ingest Endpoint

### 3.1 routes.py Modifications

File: `src/knowledge_garden/api/routes.py`

Remove:
- `import time`
- `from knowledge_garden.services.chunker import NoteChunker`
- `from knowledge_garden.services.parser import MarkdownParser`
- `class IngestRequest(BaseModel): ...`
- `class IngestResponse(BaseModel): ...`
- `@router.post("/ingest") async def ingest_vault(...): ...`

Retain unchanged:
- `class NoteSummary(BaseModel): ...`
- `class NotesListResponse(BaseModel): ...`
- `@router.get("/notes") async def list_notes(...): ...`

After this change, `routes.py` imports are:

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel
```

### 3.2 Test File Deletion

File: `tests/test_ingest_api.py`

This file is deleted entirely. No replacement test file is created (the pipeline logic is now tested in `tests/test_pipeline.py`).

### 3.3 Verification

After the deletion:
- `uv run pytest tests/ -v -m unit` must pass with no collection errors referencing `test_ingest_api.py`.
- `tests/test_notes_api.py` must still pass without modification.

---

## 4. CLI Entry Point

### 4.1 Top-level Typer App

File: `src/knowledge_garden/cli.py`

```python
from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(
    name="kg",
    help="Knowledge Garden CLI — manage your vault ingestion and explore the graph.",
    no_args_is_help=True,
)
console = Console()
```

`app` is the object referenced by `[project.scripts] kg = "knowledge_garden.cli:app"`.

### 4.2 Config and Service Initialization Helper

```python
def _load_config(config_path: str = "config.yaml") -> Config:
    """Load Config from config_path. Exits with a clean error message on failure."""
    from pathlib import Path
    from knowledge_garden.config import Config
    p = Path(config_path)
    if not p.exists():
        console.print(f"[red]Error:[/red] config file not found: {config_path}")
        raise typer.Exit(code=1)
    try:
        return Config.from_yaml(p)
    except Exception as exc:
        console.print(f"[red]Error loading config:[/red] {exc}")
        raise typer.Exit(code=1)
```

```python
def _make_graph_store(config: Config) -> Neo4jGraphStore:
    """Instantiate Neo4jGraphStore from config. Does NOT call initialize()."""
    from knowledge_garden.services.neo4j_store import Neo4jGraphStore
    return Neo4jGraphStore(config.neo4j, config.embedding)
```

```python
def _make_embedder(config: Config) -> EmbeddingService:
    """Dispatch embedder by config.embedding.provider. Raises typer.Exit on unknown provider."""
    from knowledge_garden.services.together_embedder import TogetherAIEmbedder
    from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
    provider = config.embedding.provider
    if provider == "together":
        return TogetherAIEmbedder(config.together_ai, config.embedding)
    elif provider == "huggingface":
        if config.hugging_face is None:
            console.print("[red]Error:[/red] hugging_face config section required when provider is 'huggingface'")
            raise typer.Exit(code=1)
        return HuggingFaceEmbedder(config.hugging_face, config.embedding)
    else:
        console.print(f"[red]Error:[/red] Unknown embedding provider: {provider!r}")
        raise typer.Exit(code=1)
```

These helpers are module-level functions. They are not part of any class. They are testable by calling them directly with a controlled `Config` or patched imports.

### 4.3 `kg ingest` Command

```python
@app.command()
def ingest(
    vault_name: str = typer.Argument(..., help="Name of the vault to ingest (must match config.yaml)."),
    config_path: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml."),
) -> None:
    """Ingest a vault into the Knowledge Garden graph database."""
    ...
```

**Behavior:**

1. Call `_load_config(config_path)` → `config`.
2. Look up `vault_config` in `config.vaults` by name. If not found, print `[red]Error:[/red] Vault '{vault_name}' not found in config.yaml` and `raise typer.Exit(code=1)`.
3. Build `embedder = _make_embedder(config)` and `graph_store = _make_graph_store(config)`.
4. Run `asyncio.run(_run_ingest(vault_config, config, embedder, graph_store))` where `_run_ingest` is an internal async function that:
   a. Calls `await graph_store.initialize()`.
   b. Constructs `IngestPipeline(parser, chunker, embedder, graph_store)`.
   c. Creates a `rich.progress.Progress` context. Inside the context, adds a task for `f"Ingesting {vault_name}"` with `total=None` initially.
   d. Defines a progress callback: `lambda idx, total, title: progress.update(task_id, total=total, completed=idx, description=f"[cyan]{title}[/cyan]")`.
   e. Calls `result = await pipeline.run(vault_config, progress_callback=callback)`.
   f. Closes progress context.
   g. Calls `await embedder.close()` and `await graph_store.close()`.
5. Print a `rich.table.Table` summary:

```
Ingest complete
┌──────────────────┬───────────┐
│ Metric           │ Value     │
├──────────────────┼───────────┤
│ Notes parsed     │ <n>       │
│ Chunks created   │ <n>       │
│ Duration         │ <n.nn>s   │
└──────────────────┴───────────┘
```

**Error handling:**
- If any exception is raised inside `_run_ingest` (e.g., Neo4j connection failure), catch it, print `[red]Error during ingest:[/red] {exc}`, and `raise typer.Exit(code=1)`.
- Resource cleanup (`embedder.close()`, `graph_store.close()`) must run even on failure (use try/finally).

### 4.4 `kg notes` Command

```python
@app.command()
def notes(
    vault: str | None = typer.Option(None, "--vault", "-v", help="Filter by vault name."),
    config_path: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml."),
) -> None:
    """List notes currently stored in the graph database."""
    ...
```

**Behavior:**

1. Call `_load_config(config_path)` → `config`.
2. Build `graph_store = _make_graph_store(config)`.
3. Run `asyncio.run(_run_notes(graph_store, vault_filter=vault))` where `_run_notes` is an internal async function that:
   a. Calls `await graph_store.initialize()`.
   b. Calls `all_notes = await graph_store.get_all_notes()`.
   c. If `vault_filter` is not None, filters: `all_notes = [n for n in all_notes if n.vault == vault_filter]`.
   d. Calls `await graph_store.close()`.
   e. Returns `all_notes`.
4. Print a `rich.table.Table` with columns: `ID` (first 8 chars of UUID), `Title`, `Vault`, `Path`, `Links`.
   - `ID`: `str(note.id)[:8]`
   - `Title`: `note.title`
   - `Vault`: `note.vault`
   - `Path`: `note.original_path`
   - `Links`: `str(len(note.outgoing_links))`
5. If the list is empty, print `No notes found.` instead of an empty table.

### 4.5 `kg status` Command

```python
@app.command()
def status(
    config_path: str = typer.Option("config.yaml", "--config", "-c", help="Path to config.yaml."),
) -> None:
    """Show aggregate counts of notes and chunks in the graph database."""
    ...
```

**Behavior:**

1. Call `_load_config(config_path)` → `config`.
2. Build `graph_store = _make_graph_store(config)`.
3. Run `asyncio.run(_run_status(graph_store))` where `_run_status` is an internal async function that:
   a. Calls `await graph_store.initialize()`.
   b. Calls `all_notes = await graph_store.get_all_notes()`.
   c. Calls `await graph_store.close()`.
   d. Returns `all_notes`.
4. Compute in Python (no additional graph queries):
   - `total_notes = len(all_notes)`
   - `counts_by_vault: dict[str, int]` — count of notes per `note.vault`
5. Print a `rich.table.Table` with columns: `Vault`, `Notes`.
   - One row per distinct vault name, sorted alphabetically.
   - A final row `Total` with `total_notes`.
6. If `all_notes` is empty, print `No data in graph.` and skip the table.

**Note on chunk counts:** `get_all_notes()` returns `Note` objects which do not carry chunk counts. The status command does not add new methods to `GraphStore`. Chunk counts are out of scope for this command. If chunk counts are added in a future phase, they can be incorporated then.

### 4.6 CLI Test Specifications

File: `tests/test_cli.py`

All tests are `@pytest.mark.unit`.

**Mocking strategy:** CLI commands call `asyncio.run(...)`. Unit tests patch the internal async helpers (`_run_ingest`, `_run_notes`, `_run_status`) or patch `asyncio.run` to intercept calls, and patch `_load_config`, `_make_embedder`, `_make_graph_store` as needed. Use `typer.testing.CliRunner` to invoke commands.

**Fixtures needed:**

```python
@pytest.fixture
def cli_runner():
    from typer.testing import CliRunner
    return CliRunner()

@pytest.fixture
def sample_config(tmp_path):
    """Writes a minimal valid config.yaml to tmp_path and returns a Config instance."""
    from knowledge_garden.config import (
        Config, VaultConfig, TogetherAIConfig,
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "vaults:\n"
        "  - name: my_vault\n"
        "    path: /tmp/my_vault\n"
        "together_ai:\n"
        "  api_key: fake-key\n"
    )
    return Config.from_yaml(config_path), config_path
```

#### `kg ingest` tests

| Test function | Setup | Invoke | Expected outcome |
|---|---|---|---|
| `test_ingest_vault_not_found` | Patch `_load_config` to return config with `vaults=[VaultConfig(name="other", path="/x")]` | `kg ingest missing_vault` | Exit code 1; output contains `"not found"` |
| `test_ingest_missing_config_file` | No patching; point to nonexistent config file | `kg ingest vault --config /nonexistent/config.yaml` | Exit code 1; output contains `"not found"` |
| `test_ingest_happy_path` | Patch `_load_config` to return config with one vault; patch `asyncio.run` to return `None` and set side-effect to simulate a successful `IngestResult`; OR patch `_run_ingest` directly | `kg ingest my_vault` | Exit code 0; output contains `"Notes parsed"` and `"Chunks created"` |
| `test_ingest_prints_summary_table` | Patch so `IngestResult(notes_parsed=3, chunks_created=12, duration_seconds=1.5)` is returned | `kg ingest my_vault` | Output contains `"3"` and `"12"` and `"1.5"` (or `"1.50"`) |
| `test_ingest_unknown_provider_exits` | Config has `embedding.provider = "unknown"`; do not patch `_make_embedder` | `kg ingest my_vault` | Exit code 1; output contains `"Unknown embedding provider"` |

#### `kg notes` tests

| Test function | Setup | Invoke | Expected outcome |
|---|---|---|---|
| `test_notes_empty_graph` | Patch `_load_config`; patch async helper to return `[]` | `kg notes` | Exit code 0; output contains `"No notes found"` |
| `test_notes_lists_all` | Patch async helper to return 2 Notes with titles `"Alpha"` and `"Beta"` | `kg notes` | Exit code 0; output contains `"Alpha"` and `"Beta"` |
| `test_notes_vault_filter` | Patch async helper to return 3 Notes (2 from `"vaultA"`, 1 from `"vaultB"`) | `kg notes --vault vaultA` | Output contains exactly the 2 `"vaultA"` note titles; `"vaultB"` note title absent |
| `test_notes_id_truncated` | 1 Note with a known UUID | `kg notes` | The displayed ID is the first 8 characters of the UUID string |
| `test_notes_shows_link_count` | 1 Note with `outgoing_links=["A", "B", "C"]` | `kg notes` | Output contains `"3"` in the Links column |

#### `kg status` tests

| Test function | Setup | Invoke | Expected outcome |
|---|---|---|---|
| `test_status_empty_graph` | Patch async helper to return `[]` | `kg status` | Exit code 0; output contains `"No data in graph"` |
| `test_status_shows_vault_breakdown` | Patch async helper to return 4 Notes: 3 from `"vault1"`, 1 from `"vault2"` | `kg status` | Output contains `"vault1"`, `"3"`, `"vault2"`, `"1"`, `"4"` (total) |
| `test_status_vaults_sorted_alphabetically` | 3 Notes across `"zeta"`, `"alpha"`, `"beta"` vaults | `kg status` | `"alpha"` appears before `"beta"` appears before `"zeta"` in output |
| `test_status_total_row` | 5 Notes across 2 vaults | `kg status` | Output contains `"Total"` and `"5"` |

---

## 5. Test Infrastructure

### 5.1 Additions to tests/conftest.py

No new shared fixtures are required. The existing `mock_embedder` and `mock_graph_store` fixtures from spec 01 are used in `test_pipeline.py`. The `cli_runner` and `sample_config` fixtures are defined locally in `tests/test_cli.py`.

### 5.2 New test files

| File | Purpose |
|---|---|
| `tests/test_pipeline.py` | Unit tests for `IngestPipeline` (13 test functions) |
| `tests/test_cli.py` | Unit tests for all CLI commands (14 test functions) |

### 5.3 Deleted test files

| File | Reason |
|---|---|
| `tests/test_ingest_api.py` | Endpoint removed; pipeline logic now tested in `test_pipeline.py` |

---

## 6. Implementation Notes

### asyncio.run usage in CLI

CLI commands are synchronous (Typer does not natively support async commands). Each command uses `asyncio.run(...)` to drive async service calls. The async logic is isolated into private async functions (`_run_ingest`, `_run_notes`, `_run_status`) so that unit tests can patch them independently of the sync Typer layer.

### Resource cleanup in CLI

All `embedder.close()` and `graph_store.close()` calls in the CLI are inside `try/finally` blocks to guarantee cleanup on both success and failure paths.

### IngestPipeline vs routes.py

The pipeline logic in `routes.py` (the deleted `ingest_vault` handler) is functionally identical to `IngestPipeline.run()`. The key differences are:
- `IngestPipeline` takes its dependencies as constructor arguments rather than pulling them from `app.state`.
- `IngestPipeline` exposes a `progress_callback` parameter for per-note progress reporting.
- `IngestPipeline` is fully testable without FastAPI.

### No new GraphStore methods

The `GraphStore` ABC is not modified in this phase. The `status` command computes vault breakdowns from `get_all_notes()` in Python. This is acceptable for the current scale (local personal vaults). If performance becomes a concern in a future phase, dedicated count queries can be added to `GraphStore` via a spec amendment.

### Chunk counts in status

`get_all_notes()` does not return chunk counts. The `kg status` command omits chunk counts. This is a deliberate scoping decision; see "Out of scope" in `intent.md`. A future amendment to `GraphStore` (e.g., `get_chunk_counts_by_vault() -> dict[str, int]`) could add this without breaking the current contract.
