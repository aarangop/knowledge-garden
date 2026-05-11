# 10 — Tasks

## Step 1: Service-layer `SearchResult` dataclass

- [ ] Write test: `test_search_result_dataclass_fields` — instantiate `SearchResult` with all fields; verify `note_id`, `title`, `source_vault`, `original_path`, `score`, `snippet`, `heading_context` are accessible (red)
- [ ] Verify test fails (red)
- [ ] Define `SearchResult` dataclass in `services/graph_store.py`
- [ ] Verify test passes (green)

## Step 2: GraphStore.get_note_by_id

- [ ] Write test: `test_get_note_by_id_found` — mock session returns one Note row → Note returned (red)
- [ ] Write test: `test_get_note_by_id_not_found` — mock session `.single()` returns `None` → `None` returned (red)
- [ ] Write test: `test_get_note_by_id_uuid_coerced` — UUID instance passed as `note_id` → query uses `str(note_id)` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_note_by_id` abstract method to `GraphStore`
- [ ] Implement `get_note_by_id` in `Neo4jGraphStore`
- [ ] Verify tests pass (green)

## Step 3: GraphStore.get_stats

- [ ] Write test: `test_get_stats_returns_all_keys` — mocked sessions return numeric data → dict has all six keys (red)
- [ ] Write test: `test_get_stats_vault_names_sorted` — note query returns `["z_vault", "a_vault"]` → `vault_names == ["a_vault", "z_vault"]` (red)
- [ ] Write test: `test_get_stats_empty_graph` — all queries return no rows → all int fields 0, `vault_names == []` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_stats` abstract method to `GraphStore`
- [ ] Implement `get_stats` in `Neo4jGraphStore` using five separate Cypher queries
- [ ] Verify tests pass (green)

## Step 4: GraphStore.search_notes

- [ ] Write test: `test_search_notes_returns_results` (red)
- [ ] Write test: `test_search_notes_dedup_keeps_best_score` (red)
- [ ] Write test: `test_search_notes_vault_filter` (red)
- [ ] Write test: `test_search_notes_orphaned_chunk_skipped` (red)
- [ ] Write test: `test_search_notes_sorted_by_score_desc` (red)
- [ ] Write test: `test_search_notes_limit_applied` (red)
- [ ] Write test: `test_search_notes_empty_graph` (red)
- [ ] Write test: `test_search_notes_snippet_truncated` (red)
- [ ] Write test: `test_search_notes_overfetch_factor` (red)
- [ ] Verify tests fail (red)
- [ ] Add `search_notes` abstract method to `GraphStore`
- [ ] Implement `search_notes` in `Neo4jGraphStore`
- [ ] Verify tests pass (green)

## Step 5: `SearchConfig` and `BusinessConfig.search` field

- [ ] Write test: `test_search_config_default` — `BusinessConfig()` → `business.search.search_limit == 10` (red)
- [ ] Write test: `test_search_config_from_yaml` — YAML with `search:\n  search_limit: 25` → `business.search.search_limit == 25` (red)
- [ ] Verify tests fail (red)
- [ ] Add `SearchConfig(BaseModel)` to `config.py`
- [ ] Add `search: SearchConfig = SearchConfig()` field to `BusinessConfig`
- [ ] Add `SearchConfig` to `__all__` in `config.py`
- [ ] Verify tests pass (green)

## Step 6: API Pydantic models

- [ ] Write test: `test_search_response_model_fields` — instantiate `SearchResponse` with `results=[]`, `query="q"`, `total=0` → model valid (red)
- [ ] Write test: `test_stats_response_model_fields` — instantiate `StatsResponse` with all required fields → model valid (red)
- [ ] Write test: `test_search_limit_zero_returns_422` — validate `limit=0` raises error (red)
- [ ] Write test: `test_search_limit_above_max_returns_422` — validate `limit=51` raises 422 (red)
- [ ] Verify tests fail (red)
- [ ] Add `SearchResult` (API Pydantic model), `SearchResponse`, `StatsResponse` to `api/routes.py`
- [ ] Add `from fastapi import Query` import to `api/routes.py`
- [ ] Verify tests pass (green)

## Step 7: `GET /api/v1/search` endpoint

- [ ] Write test: `test_search_returns_200` (red)
- [ ] Write test: `test_search_response_schema` (red)
- [ ] Write test: `test_search_result_fields` (red)
- [ ] Write test: `test_search_empty_results` (red)
- [ ] Write test: `test_search_vault_filter_passed` (red)
- [ ] Write test: `test_search_limit_passed` (red)
- [ ] Write test: `test_search_query_echoed` (red)
- [ ] Write test: `test_search_total_matches_results_length` (red)
- [ ] Write test: `test_search_missing_q_returns_422` (red)
- [ ] Verify tests fail (red)
- [ ] Add `search_notes` handler to `api/routes.py`
- [ ] Verify tests pass (green)

## Step 8: `GET /api/v1/stats` endpoint

- [ ] Write test: `test_stats_returns_200` (red)
- [ ] Write test: `test_stats_response_schema` (red)
- [ ] Write test: `test_stats_values_match_graph_store` (red)
- [ ] Write test: `test_stats_empty_graph` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_graph_stats` handler to `api/routes.py`
- [ ] Verify tests pass (green)

## Step 9: CLI `kg search` command

- [ ] Write test: `test_search_command_exits_zero` (red)
- [ ] Write test: `test_search_command_prints_table` (red)
- [ ] Write test: `test_search_command_no_results` (red)
- [ ] Write test: `test_search_command_vault_flag` (red)
- [ ] Write test: `test_search_command_limit_flag_overrides_config` (red)
- [ ] Write test: `test_search_command_config_not_found` (red)
- [ ] Write test: `test_search_command_settings_error` (red)
- [ ] Write test: `test_search_command_embedder_error` (red)
- [ ] Verify tests fail (red)
- [ ] Add `_run_search` coroutine to `cli.py`
- [ ] Add `search` command to `cli.py` with Rich table output
- [ ] Verify tests pass (green)

## Step 10: Final verification

- [ ] Run `ruff check src/ tests/` — zero new errors
- [ ] Run `mypy src/` — zero new errors
- [ ] Run `uv run pytest tests/ -v -m unit` — all unit tests pass
