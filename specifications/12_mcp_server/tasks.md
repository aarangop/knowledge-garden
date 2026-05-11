# 12 — Tasks

## Step 1: GraphStore.get_note_by_title

- [ ] Write test: `test_get_note_by_title_found` — mock session returns one row, expect `Note` returned (red)
- [ ] Write test: `test_get_note_by_title_case_insensitive` — query uses different casing than stored title, expect match (red)
- [ ] Write test: `test_get_note_by_title_not_found` — mock session returns no rows, expect `None` (red)
- [ ] Write test: `test_get_note_by_title_returns_first_match` — mock session returns two rows, expect first only (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_note_by_title` abstract method to `GraphStore` in `services/graph_store.py`
- [ ] Implement `get_note_by_title` in `Neo4jGraphStore` in `services/neo4j_store.py`
- [ ] Verify tests pass (green)

## Step 2: Verify spec 10 dependencies are in place

- [ ] Confirm `GraphStore.get_note_by_id(note_id: object) -> Note | None` is defined and implemented (from spec 10)
- [ ] Confirm `GraphStore.get_stats() -> dict[str, int | list[str]]` is defined and implemented with all six keys including `links_to_edge_count` (from spec 10)
- [ ] If either is missing, halt and complete spec 10 first — do not introduce forward declarations or `NotImplementedError` stubs in this spec

## Step 3: pyproject.toml changes

- [ ] Add `"mcp[cli]>=1.0.0"` to `dependencies` in `pyproject.toml`
- [ ] Add `kg-mcp = "knowledge_garden.mcp_server:main"` to `[project.scripts]` in `pyproject.toml`
- [ ] Run `uv sync` and confirm no dependency resolution errors (green)

## Step 4: MCP server — lifespan and AppState

- [ ] Create `src/knowledge_garden/mcp_server.py`
- [ ] Add module-level imports: `from mcp.server.fastmcp import FastMCP, Context`
- [ ] Define `AppState` dataclass with `graph_store: GraphStore` and `embedder: EmbeddingService`
- [ ] Implement `kg_lifespan` async context manager that yields `AppState(...)` directly (mirrors `main.py` lifespan pattern)
- [ ] Instantiate `mcp = FastMCP("Knowledge Garden", lifespan=kg_lifespan)`
- [ ] Implement `main()` calling `mcp.run()` (no transport argument — defaults to stdio)
- [ ] Verify `uv run kg-mcp --help` exits without import errors (green)

## Step 5: Tool — search_notes

- [ ] Write test: `test_search_notes_returns_json_string` — fixture sets `mock_ctx.request_context.lifespan_context = mock_state` directly; assert returned JSON array element shape matches the docstring (no `note_id` field) (red)
- [ ] Write test: `test_search_notes_empty_results` (red)
- [ ] Write test: `test_search_notes_vault_filter` (red)
- [ ] Write test: `test_search_notes_limit_passed_to_store` (red)
- [ ] Write test: `test_search_notes_limit_clamped_max` (red)
- [ ] Write test: `test_search_notes_limit_clamped_min` (red)
- [ ] Write test: `test_search_notes_threshold_passed_to_store` (red)
- [ ] Write test: `test_search_notes_skips_note_not_found` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `search_notes` tool in `mcp_server.py`; build result dicts inline and serialize via `json.dumps`; access state via `ctx.request_context.lifespan_context`
- [ ] Verify tests pass (green)

## Step 6: Tool — get_note

- [ ] Write test: `test_get_note_found` (red)
- [ ] Write test: `test_get_note_not_found` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `get_note` tool in `mcp_server.py`; access state via `ctx.request_context.lifespan_context`
- [ ] Verify tests pass (green)

## Step 7: Tool — list_vaults

- [ ] Write test: `test_list_vaults_returns_json` (red)
- [ ] Write test: `test_list_vaults_empty_graph` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `list_vaults` tool in `mcp_server.py`; access state via `ctx.request_context.lifespan_context`
- [ ] Verify tests pass (green)

## Step 8: Tool — get_graph_stats

- [ ] Write test: `test_get_graph_stats_returns_json` — fixture returns dict with all six keys including `links_to_edge_count` (red)
- [ ] Verify test fails (red)
- [ ] Implement `get_graph_stats` tool in `mcp_server.py`; access state via `ctx.request_context.lifespan_context`; return `json.dumps(stats)` unmodified
- [ ] Verify test passes (green)

## Step 9: Final verification

- [ ] Run `ruff check src/ tests/` — zero new errors
- [ ] Run `mypy src/` — zero new errors
- [ ] Run `uv run pytest tests/ -v -m unit` — all unit tests pass
- [ ] Verify `uv run kg-mcp --help` exits 0 with no import errors
