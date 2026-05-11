# 11 — Tasks

## Step 1: Note model — add `content_hash` field

- [ ] Write test: `test_note_has_content_hash_field` — construct `Note` without `content_hash`, assert attribute exists and defaults to `None` (red)
- [ ] Write test: `test_note_content_hash_accepts_string` — construct `Note` with `content_hash="abc"`, assert field is `"abc"` (red)
- [ ] Verify tests fail (red)
- [ ] Add `content_hash: str | None = None` field to `Note` in `models/note.py`
- [ ] Verify tests pass (green)

## Step 2: GraphStore — `get_all_note_paths`

- [ ] Write test: `test_get_all_note_paths_returns_dict` (red)
- [ ] Write test: `test_get_all_note_paths_empty_vault` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_all_note_paths(vault: str) -> dict[str, str | None]` abstract method to `GraphStore`
- [ ] Implement `get_all_note_paths` in `Neo4jGraphStore` (returns dict path → hash)
- [ ] Verify tests pass (green)

## Step 3: GraphStore — `get_note_by_path`

- [ ] Write test: `test_get_note_by_path_found` (red)
- [ ] Write test: `test_get_note_by_path_not_found` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_note_by_path` abstract method to `GraphStore`
- [ ] Implement `get_note_by_path` in `Neo4jGraphStore`
- [ ] Verify tests pass (green)

## Step 4: GraphStore — `delete_note`

- [ ] Write test: `test_delete_note_calls_detach_delete` (red)
- [ ] Write test: `test_delete_note_deletes_chunks` (red)
- [ ] Verify tests fail (red)
- [ ] Add `delete_note` abstract method to `GraphStore`
- [ ] Implement `delete_note` in `Neo4jGraphStore` (three-query sequence)
- [ ] Verify tests pass (green)

## Step 5: GraphStore — `set_note_content_hash`

- [ ] Write test: `test_set_note_content_hash_runs_set` (red)
- [ ] Verify test fails (red)
- [ ] Add `set_note_content_hash` abstract method to `GraphStore`
- [ ] Implement `set_note_content_hash` in `Neo4jGraphStore`
- [ ] Verify test passes (green)

## Step 6: GraphStore — `get_chunk_by_id`

- [ ] Write test: `test_get_chunk_by_id_found` (red)
- [ ] Write test: `test_get_chunk_by_id_not_found` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_chunk_by_id` abstract method to `GraphStore`
- [ ] Implement `get_chunk_by_id` in `Neo4jGraphStore`
- [ ] Verify tests pass (green)

## Step 7: GraphStore — `upsert_note` update for `content_hash`

- [ ] Write test: `test_upsert_note_persists_content_hash` (red)
- [ ] Write test: `test_upsert_note_persists_null_content_hash` (red)
- [ ] Verify tests fail (red)
- [ ] Update `upsert_note` Cypher in `Neo4jGraphStore` to include `n.content_hash = $content_hash`
- [ ] Verify tests pass (green)

## Step 8: SemanticLinker — `link_chunks` method

- [ ] Write test: `test_link_chunks_creates_similarity_edges` (red)
- [ ] Write test: `test_link_chunks_excludes_same_note` (red)
- [ ] Write test: `test_link_chunks_skips_missing_chunk` (red)
- [ ] Write test: `test_link_chunks_skips_chunk_without_embedding` (red)
- [ ] Write test: `test_link_chunks_empty_list` (red)
- [ ] Write test: `test_link_chunks_does_not_call_derive_related_to` (red)
- [ ] Write test: `test_link_chunks_progress_callback` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `link_chunks` method on `SemanticLinker` in `services/linker.py`
- [ ] Verify tests pass (green)

## Step 9: SyncPhase, SyncProgressCallback, SyncResult

- [ ] Write test: `test_sync_result_shape` — construct `SyncResult` with all fields, assert attribute access (red)
- [ ] Verify test fails (red)
- [ ] Create `services/sync_pipeline.py`
- [ ] Define `SyncPhase(StrEnum)` with `SCANNING`, `DELETING`, `EMBEDDING`, `LINKING`
- [ ] Define `SyncProgressCallback` type alias
- [ ] Define `SyncResult` dataclass with all ten fields (vault, notes_added, notes_updated, notes_deleted, notes_unchanged, chunks_added, chunks_deleted, similarity_edges_created, note_relationships_derived, duration_seconds)
- [ ] Verify test passes (green)

## Step 10: SyncPipeline — `sync` method (core logic)

- [ ] Write test: `test_sync_adds_new_notes` (red)
- [ ] Write test: `test_sync_skips_unchanged_notes` (red)
- [ ] Write test: `test_sync_updates_changed_notes` (red)
- [ ] Write test: `test_sync_deletes_removed_notes` (red)
- [ ] Write test: `test_sync_empty_vault` (red)
- [ ] Write test: `test_sync_all_unchanged` (red)
- [ ] Write test: `test_sync_mixed` (red)
- [ ] Write test: `test_sync_content_hash_stored` (red)
- [ ] Write test: `test_sync_changed_note_old_chunks_deleted` (red)
- [ ] Write test: `test_sync_linking_phase_called_for_new_chunks` (red)
- [ ] Write test: `test_sync_linking_skipped_when_no_new_chunks` (red)
- [ ] Write test: `test_sync_derives_related_to_after_linking` (red)
- [ ] Write test: `test_sync_changed_note_chunks_counted_in_chunks_deleted` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `SyncPipeline` class and `sync` method in `services/sync_pipeline.py`
  (LINKING phase calls `linker.link_chunks` and then `graph_store.derive_related_to`)
- [ ] Implement `_compute_hash` helper
- [ ] Verify tests pass (green)

## Step 11: SyncPipeline — progress callback tests

- [ ] Write test: `test_sync_progress_callback_scanning` (red)
- [ ] Write test: `test_sync_progress_callback_embedding` (red)
- [ ] Verify tests fail (red)
- [ ] Ensure `sync` emits `SyncPhase.SCANNING` and `SyncPhase.EMBEDDING` callbacks
- [ ] Verify tests pass (green)

## Step 12: CLI `kg sync` command

- [ ] Write test: `test_sync_command_exits_zero` (red)
- [ ] Write test: `test_sync_command_prints_summary` (red)
- [ ] Write test: `test_sync_command_unknown_vault_exits_nonzero` (red)
- [ ] Write test: `test_sync_command_config_not_found` (red)
- [ ] Write test: `test_sync_command_settings_error` (red)
- [ ] Verify tests fail (red)
- [ ] Add `_run_sync` coroutine to `cli.py`
- [ ] Add `sync` command to `cli.py` with Rich progress bar (four phases) and result table
- [ ] Verify tests pass (green)

## Step 13: API `POST /api/v1/sync` endpoint

- [ ] Write test: `test_sync_endpoint_returns_200` (red)
- [ ] Write test: `test_sync_endpoint_response_schema` (red)
- [ ] Write test: `test_sync_endpoint_missing_path_returns_422` (red)
- [ ] Verify tests fail (red)
- [ ] Add `SyncRequest` (vault, path) and `SyncResponse` (with similarity_edges_created and note_relationships_derived) Pydantic models to `api/routes.py`
- [ ] Add `POST /sync` route handler to `api/routes.py` — handler builds `VaultConfig` from request body and uses default `ChunkingConfig`/`EmbeddingConfig`/`DedupConfig`/`LinkingConfig`. Does NOT read `app.state.business_config`.
- [ ] No changes to `main.py` lifespan are required (`app.state.embedder` is already set).
- [ ] Verify tests pass (green)

## Step 14: Final verification

- [ ] Run `ruff check src/ tests/` — zero new errors
- [ ] Run `mypy src/` — zero new errors
- [ ] Run `uv run pytest tests/ -v -m unit` — all unit tests pass
