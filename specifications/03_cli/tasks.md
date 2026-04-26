# Tasks: CLI and Pipeline Extraction

All tasks follow TDD order: write tests first (red), then implement (green), then verify.

---

## Step 1 — Add Runtime Dependencies

- [ ] Add `"typer>=0.12.0"` and `"rich>=13.0.0"` to `[project] dependencies` in `pyproject.toml`
- [ ] Add `[project.scripts]` table with `kg = "knowledge_garden.cli:app"` to `pyproject.toml`
- [ ] Run `uv sync` and verify it exits 0
- [ ] Verify `python -c "import typer, rich"` exits 0

---

## Step 2 — IngestPipeline Service

### 2a — Write pipeline tests (red phase)

- [ ] Create `tests/test_pipeline.py`
- [ ] Add local fixtures: `mock_parser`, `mock_chunker`, `sample_vault_config_obj`, `pipeline` (as specified in contract section 2.3)
- [ ] Add local helpers: `make_note(title)`, `make_chunk(note, index)`
- [ ] Write test `test_pipeline_empty_vault` (red phase)
- [ ] Write test `test_pipeline_single_note_no_chunks` (red phase)
- [ ] Write test `test_pipeline_single_note_with_chunks` (red phase)
- [ ] Write test `test_pipeline_multiple_notes` (red phase)
- [ ] Write test `test_pipeline_embed_called_once_for_all_chunks` (red phase)
- [ ] Write test `test_pipeline_embeddings_assigned_to_chunks` (red phase)
- [ ] Write test `test_pipeline_progress_callback_not_called_for_empty_vault` (red phase)
- [ ] Write test `test_pipeline_progress_callback_called_once_per_note` (red phase)
- [ ] Write test `test_pipeline_progress_callback_receives_correct_args` (red phase)
- [ ] Write test `test_pipeline_progress_callback_is_optional` (red phase)
- [ ] Write test `test_pipeline_result_duration_non_negative` (red phase)
- [ ] Write test `test_pipeline_result_is_ingest_result` (red phase)
- [ ] Write test `test_pipeline_upsert_note_called_before_upsert_chunk` (red phase)
- [ ] Verify all 13 pipeline tests fail (red check — `IngestPipeline` does not exist yet)

### 2b — Implement IngestPipeline (green phase)

- [ ] Create `src/knowledge_garden/services/pipeline.py`
- [ ] Define `IngestResult` dataclass with `notes_parsed`, `chunks_created`, `duration_seconds` fields
- [ ] Define `ProgressCallback` type alias: `Callable[[int, int, str], None]`
- [ ] Implement `IngestPipeline.__init__` storing `parser`, `chunker`, `embedder`, `graph_store`
- [ ] Implement `IngestPipeline.run`:
  - [ ] Call `parser.parse_vault(vault_config)` to get notes list
  - [ ] Loop over notes; call `progress_callback(idx, total, note.title)` if provided (1-based idx)
  - [ ] Call `chunker.chunk_note(note)` per note; accumulate all chunks
  - [ ] If chunks exist: extract texts, call `await embedder.embed(texts)` once, assign vectors back to chunks
  - [ ] Loop `await graph_store.upsert_note(note)` for all notes
  - [ ] Loop `await graph_store.upsert_chunk(chunk)` for all chunks
  - [ ] Record `duration_seconds` via `time.monotonic()`
  - [ ] Return `IngestResult(notes_parsed, chunks_created, duration_seconds)`
- [ ] Verify all 13 pipeline tests pass (green check)

---

## Step 3 — Remove Ingest Endpoint from the API

- [ ] Delete `tests/test_ingest_api.py`
- [ ] Remove from `src/knowledge_garden/api/routes.py`:
  - [ ] `import time`
  - [ ] `from knowledge_garden.services.chunker import NoteChunker`
  - [ ] `from knowledge_garden.services.parser import MarkdownParser`
  - [ ] `class IngestRequest(BaseModel): ...`
  - [ ] `class IngestResponse(BaseModel): ...`
  - [ ] `@router.post("/ingest") async def ingest_vault(...): ...`
- [ ] Verify `uv run pytest tests/ -v -m unit` passes with no collection errors
- [ ] Verify `tests/test_notes_api.py` tests still pass

---

## Step 4 — Implement CLI Entry Point

### 4a — Write CLI tests (red phase)

- [ ] Create `tests/test_cli.py`
- [ ] Add local fixtures: `cli_runner`, `sample_config` (as specified in contract section 4.6)
- [ ] Write `kg ingest` tests (red phase):
  - [ ] `test_ingest_vault_not_found`
  - [ ] `test_ingest_missing_config_file`
  - [ ] `test_ingest_happy_path`
  - [ ] `test_ingest_prints_summary_table`
  - [ ] `test_ingest_unknown_provider_exits`
- [ ] Write `kg notes` tests (red phase):
  - [ ] `test_notes_empty_graph`
  - [ ] `test_notes_lists_all`
  - [ ] `test_notes_vault_filter`
  - [ ] `test_notes_id_truncated`
  - [ ] `test_notes_shows_link_count`
- [ ] Write `kg status` tests (red phase):
  - [ ] `test_status_empty_graph`
  - [ ] `test_status_shows_vault_breakdown`
  - [ ] `test_status_vaults_sorted_alphabetically`
  - [ ] `test_status_total_row`
- [ ] Verify all 14 CLI tests fail (red check — `src/knowledge_garden/cli.py` does not exist yet)

### 4b — Implement CLI (green phase)

- [ ] Create `src/knowledge_garden/cli.py`
- [ ] Define `app = typer.Typer(name="kg", help="...", no_args_is_help=True)` and `console = Console()`
- [ ] Implement `_load_config(config_path)`:
  - [ ] Check `Path(config_path).exists()`; print error and `raise typer.Exit(code=1)` if not
  - [ ] Call `Config.from_yaml()`; catch exceptions, print error, `raise typer.Exit(code=1)`
- [ ] Implement `_make_graph_store(config)` returning `Neo4jGraphStore(config.neo4j, config.embedding)`
- [ ] Implement `_make_embedder(config)` with provider dispatch and `typer.Exit(code=1)` on unknown provider
- [ ] Implement `ingest` command:
  - [ ] Vault lookup; exit 1 if not found
  - [ ] Call `_make_embedder` and `_make_graph_store`
  - [ ] Implement `_run_ingest` async function with `graph_store.initialize()`, `IngestPipeline`, `rich.progress.Progress` context, `pipeline.run()` with callback, and `try/finally` cleanup
  - [ ] Call `asyncio.run(_run_ingest(...))`
  - [ ] Print summary `rich.table.Table` with notes parsed, chunks created, duration
- [ ] Implement `notes` command:
  - [ ] Call `_make_graph_store`
  - [ ] Implement `_run_notes` async function: `initialize()`, `get_all_notes()`, optional vault filter, `close()`
  - [ ] Call `asyncio.run(_run_notes(...))`
  - [ ] Print `rich.table.Table` with ID (8 chars), Title, Vault, Path, Links; or `"No notes found."` if empty
- [ ] Implement `status` command:
  - [ ] Call `_make_graph_store`
  - [ ] Implement `_run_status` async function: `initialize()`, `get_all_notes()`, `close()`
  - [ ] Call `asyncio.run(_run_status(...))`
  - [ ] Compute counts by vault in Python
  - [ ] Print `rich.table.Table` with Vault and Notes columns (sorted alphabetically), Total row; or `"No data in graph."` if empty
- [ ] Verify all 14 CLI tests pass (green check)

---

## Step 5 — Register Entry Point Verification

- [ ] Run `uv sync` to pick up the new `[project.scripts]` entry
- [ ] Verify `kg --help` prints the top-level command list (manual check)
- [ ] Verify `kg ingest --help` prints the ingest command usage (manual check)
- [ ] Verify `kg notes --help` prints the notes command usage (manual check)
- [ ] Verify `kg status --help` prints the status command usage (manual check)

---

## Final Verification

- [ ] Run `uv run pytest tests/ -v -m unit` — all unit tests pass
- [ ] Confirm test count increases: Phase 01 (31) + Phase 02 minus deleted ingest tests + Phase 03 new tests
- [ ] Run `uv run ruff check src/ tests/` — exits 0
- [ ] Run `uv run mypy src/` — exits 0
- [ ] Manual smoke test: `kg ingest <vault_name>` against a real vault with a real Neo4j instance
- [ ] Confirm `GET /api/v1/notes` integration test still passes (if running against Neo4j)
