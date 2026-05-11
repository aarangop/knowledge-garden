# 09 — Tasks

## Step 1: GraphStore.get_note_relationships_with_scores

- [ ] Write test: `test_get_note_relationships_with_scores_returns_links_to` (red)
- [ ] Write test: `test_get_note_relationships_with_scores_returns_related_to` (red)
- [ ] Write test: `test_get_note_relationships_with_scores_both_types` (red)
- [ ] Write test: `test_get_note_relationships_with_scores_empty` (red)
- [ ] Verify tests fail (red)
- [ ] Add `get_note_relationships_with_scores` abstract method to `GraphStore`
- [ ] Implement `get_note_relationships_with_scores` in `Neo4jGraphStore`
- [ ] Verify tests pass (green)

## Step 2: ExportResult, ExportPhase, ExportProgressCallback

- [ ] Write test: `test_export_result_shape` — ExportResult has correct fields (red)
- [ ] Verify test fails (red)
- [ ] Define `ExportResult` dataclass in `services/exporter.py`
- [ ] Define `ExportPhase(StrEnum)` in `services/exporter.py`
- [ ] Define `ExportProgressCallback` type alias in `services/exporter.py`
- [ ] Verify test passes (green)

## Step 3: VaultExporter._build_conflict_map and _build_stem_map

- [ ] Write test: `test_build_stem_map_no_conflicts` (red)
- [ ] Write test: `test_build_stem_map_conflict_same_title_different_vaults` (red)
- [ ] Write test: `test_build_stem_map_conflict_three_notes_same_title` (red)
- [ ] Write test: `test_build_stem_map_single_note` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `VaultExporter._build_conflict_map` (static method)
- [ ] Implement `VaultExporter._build_stem_map` (static method)
- [ ] Verify tests pass (green)

## Step 4: VaultExporter._build_references_section

- [ ] Write test: `test_build_references_both_present` (red)
- [ ] Write test: `test_build_references_links_only` (red)
- [ ] Write test: `test_build_references_related_only` (red)
- [ ] Write test: `test_build_references_both_empty` (red)
- [ ] Write test: `test_build_references_links_alphabetical` (red)
- [ ] Write test: `test_build_references_related_score_order` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `VaultExporter._build_references_section` (static method)
- [ ] Verify tests pass (green)

## Step 5: VaultExporter._compose_file

- [ ] Write test: `test_compose_file_includes_frontmatter` (red)
- [ ] Write test: `test_compose_file_includes_content` (red)
- [ ] Write test: `test_compose_file_with_references` (red)
- [ ] Write test: `test_compose_file_no_references` (red)
- [ ] Write test: `test_compose_file_ends_with_newline` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `VaultExporter._compose_file` (static method)
- [ ] Verify tests pass (green)

## Step 6: VaultExporter.export

- [ ] Write test: `test_export_writes_files` (red)
- [ ] Write test: `test_export_creates_output_dir` (red)
- [ ] Write test: `test_export_conflict_resolution_filename` (red)
- [ ] Write test: `test_export_references_links_to_alphabetical` (red)
- [ ] Write test: `test_export_references_related_to_score_desc` (red)
- [ ] Write test: `test_export_skips_orphaned_targets` (red)
- [ ] Write test: `test_export_idempotent_overwrites` (red)
- [ ] Write test: `test_export_progress_callback_called` (red)
- [ ] Write test: `test_export_empty_graph` (red)
- [ ] Verify tests fail (red)
- [ ] Implement `VaultExporter.export`
- [ ] Verify tests pass (green)

## Step 7: CLI `kg export` command

- [ ] Write test: `test_export_command_exits_zero` (red)
- [ ] Write test: `test_export_command_prints_table` (red)
- [ ] Write test: `test_export_command_config_not_found` (red)
- [ ] Write test: `test_export_command_settings_error` (red)
- [ ] Verify tests fail (red)
- [ ] Add `_run_export` coroutine to `cli.py`
- [ ] Add `export` command to `cli.py` with Rich progress bar and result table
- [ ] Verify tests pass (green)

## Step 8: API `POST /api/v1/export` endpoint

- [ ] Write test: `test_export_endpoint_returns_200` (red)
- [ ] Write test: `test_export_endpoint_response_schema` (red)
- [ ] Write test: `test_export_endpoint_custom_output_dir` (red)
- [ ] Verify tests fail (red)
- [ ] Add `ExportRequest` and `ExportResponse` Pydantic models to `api/routes.py`
- [ ] Add `POST /export` route handler to `api/routes.py`
- [ ] Set `app.state.export_output_dir` during FastAPI lifespan in `main.py`
- [ ] Verify tests pass (green)

## Step 9: Integration test

- [ ] Write integration test: `test_exporter_integration_end_to_end` (marked `pytest.mark.integration`)
- [ ] Verify integration test passes against a live Neo4j instance

## Step 10: Final verification

- [ ] Run `ruff check src/ tests/` — zero new errors
- [ ] Run `mypy src/` — zero new errors
- [ ] Run `uv run pytest tests/ -v -m unit` — all unit tests pass
