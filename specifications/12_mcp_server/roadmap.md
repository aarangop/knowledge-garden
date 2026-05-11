# 12 — Roadmap

## Step 1: Add `get_note_by_title` to GraphStore

The `get_note` MCP tool needs to look up a note by title without knowing its UUID. Add a new abstract method to `GraphStore` and implement it in `Neo4jGraphStore` using a case-insensitive Cypher query.

**Done when:** `get_note_by_title("my note")` returns the correct `Note` when a match exists (any casing), and returns `None` when no note matches the query.

## Step 2: Implement `mcp_server.py` with all four tools

Create `src/knowledge_garden/mcp_server.py`. Use `mcp.server.fastmcp.FastMCP` with a lifespan context manager that initializes `Neo4jGraphStore` and the embedder on startup and closes them on shutdown. Implement the four tools: `search_notes`, `get_note`, `list_vaults`, `get_graph_stats`. Tools build response dicts inline and serialize with `json.dumps`; no internal `SearchResult` type is introduced (avoids name collision with the Pydantic `SearchResult` defined for the FastAPI surface in spec 10).

**Done when:** All four tool functions are importable and can be called directly in tests with mocked services. `main()` calls `mcp.run()` and registers as the `kg-mcp` script entry point.

## Step 3: Add `mcp[cli]` dependency and `kg-mcp` script entry

Update `pyproject.toml` to add `mcp[cli]>=1.0.0` to the runtime dependencies and add `kg-mcp = "knowledge_garden.mcp_server:main"` to `[project.scripts]`. Run `uv sync` to confirm no dependency conflicts.

**Done when:** `uv run kg-mcp --help` exits without import errors.

## Step 4: Unit tests for all four tools

Write `tests/test_mcp_server.py` with mocked `graph_store` and `embedder`. Cover happy paths, empty results, and error paths for each tool. Inject `AppState` via `mock_ctx.request_context.lifespan_context = mock_state` (matching the implementation, which reads `ctx.request_context.lifespan_context` directly as `AppState`).

**Done when:** All unit tests pass with `pytest -m unit`.

## Step 5: Final verification

Run `ruff check src/ tests/`, `mypy src/`, and the full unit test suite. Confirm the `kg-mcp` script entry is present and importable. This spec assumes spec 10 has already been implemented — `GraphStore.get_note_by_id` and `GraphStore.get_stats` must exist before this step.

**Done when:** Zero new lint/type errors introduced by this spec. All unit tests pass.
