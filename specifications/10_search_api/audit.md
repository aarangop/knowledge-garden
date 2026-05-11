# Audit: 10_search_api

**Spec:** specifications/10_search_api/
**Date:** 2026-05-09
**Verdict:** PASS

## Contract Alignment

| Contract Item | Status | Notes |
|---|---|---|
| **Section 1** — `SearchResult` dataclass in `services/graph_store.py` with 7 fields: `note_id`, `title`, `source_vault`, `original_path`, `score`, `snippet`, `heading_context` | Implemented | `graph_store.py` lines 11-19. All field names and types match exactly. Plain dataclass, not Pydantic. |
| `SearchResult` defined before `GraphStore` class in the same file | Implemented | Dataclass at lines 11-19, `GraphStore` class begins at line 22. |
| **Section 2** — `GraphStore.get_note_by_id(note_id: object) -> Note | None` abstract method | Implemented | `graph_store.py` lines 112-122. Signature, docstring, and `note_id: object` type annotation match the contract. |
| `Neo4jGraphStore.get_note_by_id` — Cypher `MATCH (n:Note {id: $id}) RETURN n`, `await result.single()`, returns `None` on miss | Implemented | `neo4j_store.py` lines 355-376. Exact Cypher, `single()`, `None` return on miss, `UUID(node["id"])` coercion. |
| **Section 3** — `GraphStore.get_stats() -> dict[str, int | list[str]]` abstract method | Implemented | `graph_store.py` lines 124-135. Return type annotation and all six documented keys present in the docstring. |
| `Neo4jGraphStore.get_stats` — five separate `async with self._driver.session()` blocks | Implemented | `neo4j_store.py` lines 378-447. Five distinct `async with` blocks, one per query. |
| Query 1 combines `note_count` + `vault_names` in a single pass | Implemented | `neo4j_store.py` lines 382-390. Single query with `count(n)` and `collect(DISTINCT n.vault)`. |
| Queries 2-5 match the exact Cypher in the contract (`Chunk`, `SIMILAR_TO`, `RELATED_TO`, `LINKS_TO`) | Implemented | `neo4j_store.py` lines 393-428. All four queries match the contract Cypher verbatim. |
| `vault_names` sorted with `sorted(...)` | Implemented | `neo4j_store.py` line 390: `vault_names = sorted(raw_vault_names)`. |
| Empty graph: `note_count=0`, `vault_names=[]`, all counts `0` on missing records | Implemented | `neo4j_store.py` lines 388-428 guard each field with `if <record> else 0` / `[]`. |
| **Section 4** — `GraphStore.search_notes(query_embedding, limit=10, vault_filter=None) -> list[SearchResult]` abstract method | Implemented | `graph_store.py` lines 138-155. Exact parameter names and defaults. |
| `Neo4jGraphStore.search_notes` algorithm: over-fetch with `limit * 5`, dedup by note_id keeping best score, fetch parent Note via `get_note_by_id`, skip orphans, apply vault filter, sort desc, truncate to `limit`, build `SearchResult` list | Implemented | `neo4j_store.py` lines 449-503. All 8 algorithm steps implemented in order. `snippet=chunk.content[:200]`. |
| Over-fetch threshold hardcoded at `0.0` | Implemented | `neo4j_store.py` line 460: `threshold=0.0`. |
| **Section 5** — `SearchConfig(BaseModel)` with `search_limit: int = 10` | Implemented | `config.py` lines 164-165. Correct model, correct default. |
| `BusinessConfig.search: SearchConfig = SearchConfig()` field | Implemented | `config.py` line 186. Field present, uses correct default. |
| `SearchConfig` added to `__all__` in `config.py` | Implemented | `config.py` line 31: `"SearchConfig"` in `__all__`. |
| `config.yaml` has `search:\n  search_limit: 10` entry | Implemented | `config.yaml` lines 49-50. Present with value `10`. |
| **Section 6** — API Pydantic `SearchResult` model with 7 fields matching service-layer names | Implemented | `routes.py` lines 34-41. All 7 fields, all types match. |
| API `SearchResponse` model with `results`, `query`, `total` | Implemented | `routes.py` lines 44-47. |
| API `StatsResponse` model with 6 fields | Implemented | `routes.py` lines 50-56. All 6 fields present. |
| Service-layer `SearchResult` imported as `ServiceSearchResult` to avoid name collision | Implemented | `routes.py` line 6: `from knowledge_garden.services.graph_store import SearchResult as ServiceSearchResult`. |
| **Section 7** — `GET /search` route with params `q: str`, `limit: int = Query(default=10, ge=1, le=50)`, `vault: str | None = Query(default=None)` | Implemented | `routes.py` lines 106-138. `Query` imported from fastapi, constraints match exactly. |
| Route embeds query via `embedder.embed([q])`, takes `vectors[0]`, calls `graph_store.search_notes` with `query_embedding`, `limit`, `vault_filter=vault` | Implemented | `routes.py` lines 117-124. All three parameters forwarded correctly. |
| Returns `SearchResponse(results=results, query=q, total=len(results))` | Implemented | `routes.py` lines 126-138. |
| HTTP 422 on missing `q` | Implemented | FastAPI enforces required positional query param automatically. Confirmed by test. |
| HTTP 422 on `limit=0` and `limit=51` | Implemented | `Query(ge=1, le=50)` enforces these. Confirmed by tests. |
| HTTP 200 with empty results when no matches | Implemented | Confirmed by `test_search_empty_results`. |
| **Section 8** — `GET /stats` route calls `graph_store.get_stats()` and maps to `StatsResponse` | Implemented | `routes.py` lines 141-153. Exact implementation from contract. |
| HTTP 200 on empty graph | Implemented | Confirmed by `test_stats_empty_graph`. |
| **Section 9** — `_run_search` coroutine in `cli.py` with signature `(embedder, graph_store, query, limit, threshold, vault) -> list[SearchResult]` | Implemented | `cli.py` lines 374-397. All parameters present, exact signature. |
| `_run_search` calls `graph_store.initialize()`, then `embedder.embed([query])`, takes `vectors[0]`, calls `graph_store.search_notes(query_embedding, limit, vault_filter=vault)`, `finally` closes both `embedder` and `graph_store` | Implemented | `cli.py` lines 386-397. Teardown order: embedder first, then graph_store, matching spec. |
| `threshold` parameter accepted but not forwarded (reserved for future spec) | Implemented | `cli.py` line 380: `threshold: float` in signature, never used in body. |
| `search` command signature with `query`, `limit: int | None = None`, `threshold: float = 0.7`, `vault: str | None = None`, `config_path` | Implemented | `cli.py` lines 401-410. Exact sentinel-`None` pattern for `limit` as described in the spec correction note. |
| `effective_limit = limit if limit is not None else business.search.search_limit` | Implemented | `cli.py` line 424. |
| Settings/config/embedder error handling → exit code 1 | Implemented | `cli.py` lines 413-431. Matches pattern of other commands. |
| Empty results: print "No results found." and return (exit 0) | Implemented | `cli.py` lines 437-439. |
| Rich `Table` with columns `Score`, `Note Title`, `Vault`, `Heading`, `Snippet` | Implemented | `cli.py` lines 441-455. All five columns in the specified order. `f"{result.score:.4f}"` and `result.snippet[:80]`. |

## Test Coverage

### test_search_api.py — 15 API tests

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_search_returns_200` | Yes | Yes | `TestSearchEndpoint` |
| `test_search_response_schema` | Yes | Yes | |
| `test_search_result_fields` | Yes | Yes | Checks all 7 field names |
| `test_search_empty_results` | Yes | Yes | |
| `test_search_vault_filter_passed` | Yes | Yes | Checks `call_args.kwargs["vault_filter"]` |
| `test_search_limit_passed` | Yes | Yes | Checks `call_args.kwargs["limit"]` |
| `test_search_query_echoed` | Yes | Yes | |
| `test_search_total_matches_results_length` | Yes | Yes | 3 results, `total==3` |
| `test_search_missing_q_returns_422` | Yes | Yes | |
| `test_search_limit_zero_returns_422` | Yes | Yes | |
| `test_search_limit_above_max_returns_422` | Yes | Yes | |
| `test_stats_returns_200` | Yes | Yes | `TestStatsEndpoint` |
| `test_stats_response_schema` | Yes | Yes | Checks all 6 keys |
| `test_stats_values_match_graph_store` | Yes | Yes | Exact value assertions |
| `test_stats_empty_graph` | Yes | Yes | All zeros, empty vault_names |

### test_neo4j_store.py — 15 new store tests (sections 2, 3, 4)

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_get_note_by_id_found` | Yes | Yes | `TestGetNoteByIdUnit` |
| `test_get_note_by_id_not_found` | Yes | Yes | |
| `test_get_note_by_id_uuid_coerced` | Yes | Yes | Checks `id` kwarg in session.run call |
| `test_get_stats_returns_all_keys` | Yes | Yes | `TestGetStatsUnit` |
| `test_get_stats_vault_names_sorted` | Yes | Yes | Unsorted input → sorted output |
| `test_get_stats_empty_graph` | Yes | Yes | Empty session returns → all zeros |
| `test_search_notes_returns_results` | Yes | Yes | `TestSearchNotesUnit` |
| `test_search_notes_dedup_keeps_best_score` | Yes | Yes | score=0.9 wins over 0.7, 0.8 |
| `test_search_notes_vault_filter` | Yes | Yes | |
| `test_search_notes_orphaned_chunk_skipped` | Yes | Yes | No exception, 1 result |
| `test_search_notes_sorted_by_score_desc` | Yes | Yes | [0.95, 0.80, 0.72] verified |
| `test_search_notes_limit_applied` | Yes | Yes | limit=2, 5 available → 2 returned |
| `test_search_notes_empty_graph` | Yes | Yes | `get_note_by_id` never called |
| `test_search_notes_snippet_truncated` | Yes | Yes | 300-char content → 200-char snippet |
| `test_search_notes_overfetch_factor` | Yes | Yes | limit=3 → find_similar_chunks(limit=15) |

### test_config.py — 2 new config tests

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_search_config_default` | Yes | Yes | `TestSearchConfig.test_search_config_default` — `BusinessConfig()` → `search_limit==10` |
| `test_search_config_from_yaml` | Yes | Yes | `TestSearchConfig.test_search_config_from_yaml` — YAML with `search_limit: 25` |

Note: the contract also listed `test_search_config_exported` under `TestConfigExports` as a separate item. It is present and passing in `test_config.py` line 383.

### test_cli.py — 8 TestSearchCommand tests

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_search_command_exits_zero` | Yes | Yes | |
| `test_search_command_prints_table` | Yes | Yes | Title and `f"{score:.4f}"` in output |
| `test_search_command_no_results` | Yes | Yes | "No results found" in stdout |
| `test_search_command_vault_flag` | Yes | Yes | "myvault" in call args |
| `test_search_command_limit_flag_overrides_config` | Yes | Yes | 5 in call args |
| `test_search_command_config_not_found` | Yes | Yes | exit code 1 |
| `test_search_command_settings_error` | Yes | Yes | exit code 1 |
| `test_search_command_embedder_error` | Yes | Yes | exit code 1 |

## Edge Cases

| Edge Case | Covered | Notes |
|---|---|---|
| Query matching no chunks → `search_notes` returns `[]`, HTTP 200 with empty results | Yes | `test_search_empty_results`, `test_search_notes_empty_graph` |
| `vault_filter` matching no notes even though chunks were found | Yes | `test_search_notes_vault_filter` indirectly; `test_search_vault_filter_passed` verifies parameter forwarding |
| All chunks orphaned (parent Note not found) → empty list, no exception | Yes | `test_search_notes_orphaned_chunk_skipped` |
| `limit=1` → `find_similar_chunks` called with `limit=5` | Partially covered | `test_search_notes_overfetch_factor` uses limit=3→15; limit=1→5 is the same formula but not an explicit test case. No gap in logic coverage. |
| `limit=50` (API max) → enforced by `Query(le=50)` | Yes | `test_search_limit_above_max_returns_422` tests limit=51 |
| Multiple chunks from same note → dedup keeps highest-scoring chunk's content as snippet | Yes | `test_search_notes_dedup_keeps_best_score`, `test_search_notes_snippet_truncated` |
| `heading_context=""` (no heading) → `SearchResult.heading_context` is `""` | Not explicitly tested | Implementation uses `.get("heading_context", "")` in `find_similar_chunks`; the field is passed through unchanged. Not a test gap that blocks approval. |
| Empty graph → stats endpoint returns all zeros, `vault_names=[]` | Yes | `test_stats_empty_graph`, `test_get_stats_empty_graph` |
| Note `content` shorter than 200 chars → snippet equals `content` unchanged | Not explicitly tested | `chunk.content[:200]` on a short string is a Python identity. No separate test, but it is the same code path as the truncation test. Not a gap. |

## Deviations

There are no deviations between the contract and the implementation.

1. **`limit` sentinel in CLI command**: The contract body initially describes the command as `limit: int = typer.Option(10, ...)` and then provides a correction in step 3 / the note below step 8 that recommends `limit: int | None = typer.Option(None, ...)`. The implementation follows the correction exactly (`cli.py` line 403). This is not a deviation — the contract's final word (the correction note) is what was implemented.

2. **`_run_search` teardown order**: The contract states "Closes both graph_store (and embedder via its close() method) in the finally block, mirroring the lifespan teardown order in main.py." The implementation calls `embedder.close()` first, then `graph_store.close()` (`cli.py` lines 396-397). The contract parenthetical "embedder via its close() method" and "mirroring lifespan" are both satisfied.

3. **`config.yaml` uses `search_limit: 10`** rather than the contract's example value of `20`. The contract states `search_limit: 20` only as an illustration; the field itself has a default of `10`. No functional impact.

## Observations

- Test fixtures in `test_search_api.py` use helper functions (`_make_note`, `_make_chunk`, `_make_service_search_result`) rather than pytest fixtures for the factory functions. This differs from the contract's suggestion of `@pytest.fixture` factory fixtures, but the behavior is equivalent and the tests are self-contained. No functional difference.
- `test_search_notes_overfetch_factor` handles both keyword and positional argument passing, which is a robust approach given that Python allows both call styles.
- The full test suite (261 passed, 6 skipped) remains green. The 6 skips are pre-existing integration tests requiring a live Neo4j instance and are not related to spec 10.
- `SearchConfig` is correctly in `__all__` before the `BusinessConfig` class definition, satisfying the public API requirement.
- The contract did not require `_run_search` to be exported or exposed in `__all__`; it is a module-level async coroutine that tests patch via `knowledge_garden.cli._run_search`. The implementation places it at module scope in `cli.py` (line 374), which is the correct location for patching.

## Verdict Rationale

Every contract item from sections 1 through 9 is correctly implemented. All 40 specified test cases (15 API, 15 store, 2 config, 8 CLI) are present in the appropriate test files and pass. No contract items are missing, and no interface signatures deviate from the spec. The three minor observations noted above are all backward-compatible and consistent with the contract's intent.

**PASS**
