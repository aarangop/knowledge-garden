# Audit: 12_mcp_server

**Spec:** specifications/12_mcp_server/
**Date:** 2026-05-10
**Verdict:** PASS WITH NOTES

## Contract Alignment

### §1 — `GraphStore.get_note_by_title`

| Contract Item | Status | Evidence |
|---|---|---|
| New abstract method on `GraphStore` with exact signature `async def get_note_by_title(self, title: str) -> Note \| None` | Implemented | `src/knowledge_garden/services/graph_store.py:134-147` (abstract method + matching docstring) |
| Neo4j implementation present | Implemented | `src/knowledge_garden/services/neo4j_store.py:432-457` |
| Cypher matches contract exactly (`MATCH (n:Note) WHERE toLower(n.title) = toLower($title) RETURN n LIMIT 1`) | Implemented | `neo4j_store.py:438-441` — `"MATCH (n:Note) " "WHERE toLower(n.title) = toLower($title) " "RETURN n " "LIMIT 1"` is identical when concatenated |
| Returns `None` on no row | Implemented | `neo4j_store.py:446-447` |
| Reconstructs `Note` from node properties (same shape as `get_all_notes`) | Implemented | `neo4j_store.py:449-457` (id/title/content/vault/original_path/frontmatter via `_deserialize_frontmatter`) |

### §2 — Reuse of spec 10 methods

| Contract Item | Status | Evidence |
|---|---|---|
| `get_note_by_id` reused unchanged (no redeclare/stub) | Implemented | abstract method at `graph_store.py:121-132` (from spec 10); MCP tool calls it at `mcp_server.py:105` |
| `get_stats` reused unchanged with six keys | Implemented | abstract at `graph_store.py:149-161`; MCP tool calls it at `mcp_server.py:184` |

### §3 — MCP server module (`src/knowledge_garden/mcp_server.py`)

| Contract Item | Status | Evidence |
|---|---|---|
| Module-level imports match contract block | Implemented (with one addition — see deviation #3) | `mcp_server.py:8-26`. Adds `from mcp.server.session import ServerSession` to support parameterized `Context`. All other imports identical. |
| `AppState` dataclass with `graph_store: GraphStore`, `embedder: EmbeddingService` | Implemented | `mcp_server.py:29-34` |
| `kg_lifespan` async ctx-mgr yielding `AppState` directly | Implemented | `mcp_server.py:37-57` |
| Lifespan: build `Neo4jGraphStore(settings.neo4j, embedding_config)`, `await initialize()` | Implemented | `mcp_server.py:43-44` |
| Lifespan: pick HF embedder when `settings.hugging_face is not None`, else Together | Implemented | `mcp_server.py:46-51` |
| Lifespan closes `embedder` and `graph_store` in `finally` | Implemented | `mcp_server.py:53-57` (`await embedder.close()`, `await graph_store.close()`) |
| `FastMCP("Knowledge Garden", lifespan=kg_lifespan)` | Implemented | `mcp_server.py:60` |
| Context retrieval pattern `state: AppState = ctx.request_context.lifespan_context` in every tool | Implemented | `mcp_server.py:90, 139, 157, 182` |
| `search_notes` signature (`query`, `limit=10`, `threshold=0.7`, `vault=None`, `ctx`) returns `str` | Implemented | `mcp_server.py:67-74` |
| `search_notes`: limit clamping `max(1, min(limit, 50))` | Implemented | `mcp_server.py:92` |
| `search_notes`: embed query, take vectors[0] | Implemented | `mcp_server.py:94-95` |
| `search_notes`: call `find_similar_chunks(embedding=, limit=, threshold=)` with clamped limit and threshold passed through | Implemented | `mcp_server.py:97-101` |
| `search_notes`: skip when `get_note_by_id` returns None | Implemented | `mcp_server.py:105-107` |
| `search_notes`: vault filter | Implemented | `mcp_server.py:108-109` |
| `search_notes`: result dict has exactly the 6 documented fields (no `note_id`) | Implemented | `mcp_server.py:110-119` — keys: note_title, source_vault, chunk_content, heading_context, score, original_path |
| `search_notes`: `json.dumps(results)` — returns `"[]"` for no results | Implemented | `mcp_server.py:121` (default `[]` serialises to `"[]"`) |
| `get_note` signature `(title, ctx)` → `str` | Implemented | `mcp_server.py:124-128` |
| `get_note`: not-found path returns exactly `f"Note not found: {title!r}"` | Implemented | `mcp_server.py:142-143` |
| `get_note`: found path returns `note.content` | Implemented | `mcp_server.py:144` |
| `list_vaults` (ctx) → JSON of `{vault, note_count}` aggregated from `get_all_notes` | Implemented | `mcp_server.py:147-166` |
| `list_vaults` returns `"[]"` when no notes | Implemented | `mcp_server.py:165-166` (empty list → `json.dumps([])` = `"[]"`) |
| `get_graph_stats` returns `json.dumps(stats)` unmodified | Implemented | `mcp_server.py:184-185` (no field renaming; six-key dict passed straight through) |
| `main()` calls `mcp.run()` (no transport arg → stdio) | Implemented | `mcp_server.py:188-190` |

### §5 — `pyproject.toml`

| Contract Item | Status | Evidence |
|---|---|---|
| `mcp[cli]>=1.0.0` in dependencies | Implemented | `pyproject.toml:21` |
| `kg-mcp = "knowledge_garden.mcp_server:main"` in `[project.scripts]` | Implemented | `pyproject.toml:26` |

### §4, §6 — Configuration / Claude Desktop

| Contract Item | Status | Evidence |
|---|---|---|
| No new `AppSettings` fields | Implemented | No changes to `config.py` for spec 12 surface |
| Claude Desktop block is informational only | N/A | Documentation; not a code clause |

## Test Coverage

### `tests/test_mcp_server.py` (13 tests)

| Specified Test | Present | Passing | Evidence |
|---|---|---|---|
| test_search_notes_returns_json_string | Yes | Yes | `test_mcp_server.py:115-150` — asserts all 6 keys present and `note_id` absent |
| test_search_notes_empty_results | Yes | Yes | `test_mcp_server.py:153-161` |
| test_search_notes_vault_filter | Yes | Yes | `test_mcp_server.py:164-189` |
| test_search_notes_limit_passed_to_store | Yes | Yes | `test_mcp_server.py:192-202` |
| test_search_notes_limit_clamped_max | Yes | Yes | `test_mcp_server.py:205-214` (limit=200 → 50) |
| test_search_notes_limit_clamped_min | Yes | Yes | `test_mcp_server.py:217-226` (limit=0 → 1) |
| test_search_notes_threshold_passed_to_store | Yes | Yes | `test_mcp_server.py:229-238` |
| test_search_notes_skips_note_not_found | Yes | Yes | `test_mcp_server.py:241-252` |
| test_get_note_found | Yes | Yes | `test_mcp_server.py:263-273` |
| test_get_note_not_found | Yes | Yes | `test_mcp_server.py:275-284` |
| test_list_vaults_returns_json | Yes | Yes | `test_mcp_server.py:295-313` |
| test_list_vaults_empty_graph | Yes | Yes | `test_mcp_server.py:315-324` |
| test_get_graph_stats_returns_json | Yes | Yes | `test_mcp_server.py:335-354` — asserts all six keys including `links_to_edge_count` |

### `tests/test_neo4j_store.py::TestGetNoteByTitleUnit` (4 tests)

| Specified Test | Present | Passing | Evidence |
|---|---|---|---|
| test_get_note_by_title_found | Yes | Yes | `test_neo4j_store.py:1068-1094` |
| test_get_note_by_title_case_insensitive | Yes | Yes | `test_neo4j_store.py:1096-1126` — asserts `toLower` appears in the Cypher |
| test_get_note_by_title_not_found | Yes | Yes | `test_neo4j_store.py:1128-1144` |
| test_get_note_by_title_returns_first_match | Yes | Yes | `test_neo4j_store.py:1146-1176` — asserts `LIMIT 1` appears in the Cypher |

### Test run results

- `uv run pytest tests/test_mcp_server.py tests/test_neo4j_store.py::TestGetNoteByTitleUnit -v -m unit` → **17 passed**.
- `uv run pytest tests/ -m unit` → **298 passed, 20 deselected**. No regressions.

## Edge Cases (§8)

| Edge Case | Covered | Evidence |
|---|---|---|
| `search_notes` with no notes ingested → `"[]"` | Yes | `test_search_notes_empty_results` |
| `get_note` with empty title → not-found message | Implicit | code path is exercised by `test_get_note_not_found` (mock returns None for any title, including empty) |
| `list_vaults` before any ingestion → `"[]"` | Yes | `test_list_vaults_empty_graph` |
| `get_stats` exception propagates | Implicit | No try/except in `get_graph_stats` (`mcp_server.py:184-185`) — exception propagates naturally |
| Embedder failure propagates | Implicit | No try/except in `search_notes` — exception propagates |
| Missing `TOGETHER_API_KEY` → `ValidationError` in lifespan | Implicit | `AppSettings()` call at `mcp_server.py:40` will validate at startup |

## Deviations (disclosed by executor)

### Deviation 1 — Dropped `# type: ignore[call-arg]` on `AppSettings()`

- **Where:** `mcp_server.py:40` — `settings = AppSettings()` (contract example at §3 shows `# type: ignore[call-arg]`).
- **Verdict:** **Acceptable.** Contract semantics are unchanged (still instantiates `AppSettings()` with no args, relying on env-var population). The contract's comment was a guidance hint, not a behavior clause. Mypy reports the ignore as unused under the current `pyproject` config, so retaining it would create a new lint error. Preserving zero new mypy errors (tasks §9) takes precedence.

### Deviation 2 — Stub `get_note_by_title` added to in-test `ConcreteGraphStore`

- **Where:** `tests/test_interfaces.py:150` (`async def get_note_by_title(self, title: str) -> None:`) and `tests/test_interfaces.py:102, 166`.
- **Verdict:** **Acceptable.** This is a test-internal completeness stub. Without it, `ConcreteGraphStore` cannot instantiate (the new abstract method makes it incomplete) and the abstract-completeness assertion in `test_interfaces.py` would fail. The disclosed precedent (spec 10 used the same pattern when adding `get_note_by_id` / `get_stats`) confirms this is consistent project practice. Contract behavior is unaffected — `Neo4jGraphStore` provides the production implementation.

### Deviation 3 — `Context` parameterized as `Context[ServerSession, AppState, object]`

- **Where:** `mcp_server.py:17` (`from mcp.server.session import ServerSession`), `mcp_server.py:64` (`KGContext = Context[ServerSession, AppState, object]`), tool params using `ctx: KGContext = ...`.
- **Verdict:** **Acceptable.** Functionally equivalent to bare `Context` at runtime (MCP SDK injects the same value); only the type parameter is more specific. The contract's import block listed bare `Context`, but `Context` in the SDK is a generic, and parameterizing it satisfies strict-mypy `type-arg` without altering observable behavior. The added import (`ServerSession`) is purely for type-arguments and adds no runtime surface. The `# type: ignore[assignment]` markers on default `...` values are unrelated to the parameterization and address the SDK's sentinel-default pattern.

## Observations

- Contract §3 specifies `state: AppState = ctx.request_context.lifespan_context  # type: ignore[assignment]`. The implementation drops the `[assignment]` ignore at the assignment site but adds `# type: ignore[assignment]` on the tool default-value `ctx: KGContext = ...` parameters. Net effect on mypy noise is comparable; behavior unchanged.
- `list_vaults` JSON order depends on insertion order of `dict[str, int]` (Python 3.7+ guarantees insertion-order iteration). The test (`test_list_vaults_returns_json`) correctly converts to a dict-by-vault before asserting, so order is not contractually pinned — fine.
- `mcp.tool()` decorator is applied in place, so the underlying tool functions are still importable and callable directly in tests (the test pattern relies on this). Confirmed by `from knowledge_garden.mcp_server import search_notes, get_note, list_vaults, get_graph_stats` succeeding.
- The `logger` defined at module level is unused. Not a contract violation; future cleanup candidate.

## Verdict Rationale

**PASS WITH NOTES.**

Every clause of the frozen contract for spec 12 maps to working code:
- The new `GraphStore.get_note_by_title` abstract method and its Neo4j implementation match the contract Cypher byte-for-byte.
- All four MCP tools have the specified signatures, control flow, and return-value shapes (limit clamping, vault filter, note-None skip, `Note not found: {title!r}`, unmodified six-key `get_graph_stats`).
- The lifespan correctly initializes Neo4j + embedder and closes both in `finally`.
- All 17 newly specified tests are present, marked `unit`, and pass. The full unit suite (298 tests) shows no regressions.
- `pyproject.toml` has both the new dependency and the `kg-mcp` script.

The three disclosed deviations are minor, justified, and preserve contract semantics. No clause is missing, no specified test is absent or failing, and no scope creep is observed beyond the type-narrowing `ServerSession` import used solely for a generic type parameter.

Relevant absolute paths:
- /Users/andresarango/repos/knowledge_garden/src/knowledge_garden/mcp_server.py
- /Users/andresarango/repos/knowledge_garden/src/knowledge_garden/services/graph_store.py
- /Users/andresarango/repos/knowledge_garden/src/knowledge_garden/services/neo4j_store.py
- /Users/andresarango/repos/knowledge_garden/tests/test_mcp_server.py
- /Users/andresarango/repos/knowledge_garden/tests/test_neo4j_store.py
- /Users/andresarango/repos/knowledge_garden/tests/test_interfaces.py
- /Users/andresarango/repos/knowledge_garden/pyproject.toml
