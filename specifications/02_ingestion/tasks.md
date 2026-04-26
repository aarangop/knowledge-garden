# Tasks: Vault Ingestion

All tasks follow TDD order: write tests first (red), then implement (green), then verify.

---

## Step 0 — Note Model Amendment

- [x] Write test `test_note_attachment_refs_default_empty` in `tests/test_models.py` (red phase)
- [x] Verify the test fails (red check — field does not exist yet)
- [x] Add `attachment_refs: list[str] = []` field to `Note` in `src/knowledge_garden/models/note.py`
- [x] Verify `test_note_attachment_refs_default_empty` passes (green check)

---

## Step 1 — Markdown Parser Service

- [x] Create `tests/fixtures/sample_vault/` directory with `note_a.md`, `note_b.md`, and `subdir/note_c.md` as specified in contract section 8.1
- [x] Add `sample_vault_config` fixture to `tests/conftest.py` as specified in contract section 8.2
- [x] Write tests for `MarkdownParser.extract_wikilinks` in `tests/test_parser.py` (red phase)
  - [x] `test_extract_wikilinks_simple`
  - [x] `test_extract_wikilinks_with_alias`
  - [x] `test_extract_wikilinks_multiple`
  - [x] `test_extract_wikilinks_no_links`
  - [x] `test_extract_wikilinks_empty_string`
  - [x] `test_extract_wikilinks_preserves_duplicates`
  - [x] `test_extract_wikilinks_heading_fragment`
  - [x] `test_extract_wikilinks_heading_and_alias`
  - [x] `test_extract_wikilinks_transclusion_note`
  - [x] `test_extract_wikilinks_transclusion_heading`
  - [x] `test_extract_wikilinks_transclusion_image`
  - [x] `test_extract_wikilinks_transclusion_pdf`
  - [x] `test_extract_wikilinks_standard_attachment`
  - [x] `test_extract_wikilinks_mixed`
- [x] Write tests for `MarkdownParser.parse_file` in `tests/test_parser.py` (red phase)
  - [x] `test_parse_file_sets_title_from_stem`
  - [x] `test_parse_file_sets_outgoing_links`
  - [x] `test_parse_file_sets_attachment_refs`
- [x] Write tests for `MarkdownParser.parse_vault` in `tests/test_parser.py` (red phase)
  - [x] `test_parse_vault_empty_directory`
  - [x] `test_parse_vault_skips_non_md_files`
  - [x] `test_parse_vault_single_note`
  - [x] `test_parse_vault_original_path`
  - [x] `test_parse_vault_nested_directories`
  - [x] `test_parse_vault_mixed_files`
  - [x] `test_parse_vault_no_links`
  - [x] `test_parse_vault_note_has_uuid`
- [x] Verify all parser tests fail (red check — `MarkdownParser` does not exist yet)
- [x] Create `src/knowledge_garden/services/parser.py` with `MarkdownParser` class implementing `extract_wikilinks`, `parse_file`, and `parse_vault`
- [x] Verify all parser tests pass (green check)

---

## Step 2 — Chunker Service

- [x] Add `default_chunking_config` and `small_chunking_config` fixtures to `tests/conftest.py` as specified in contract section 8.2
- [x] Write tests for `NoteChunker.chunk_note` in `tests/test_chunker.py` (red phase)
  - [x] `test_chunk_note_no_headings`
  - [x] `test_chunk_note_no_headings_below_min`
  - [x] `test_chunk_note_single_h2`
  - [x] `test_chunk_note_h1_splits_content`
  - [x] `test_chunk_note_multiple_h2`
  - [x] `test_chunk_note_sequential_indices`
  - [x] `test_chunk_note_sets_note_id`
  - [x] `test_chunk_note_embedding_is_none`
  - [x] `test_chunk_note_oversized_section_split_by_paragraph`
  - [x] `test_chunk_note_paragraph_split_inherits_heading_context`
  - [x] `test_chunk_note_below_min_discarded`
  - [x] `test_chunk_note_empty_content`
  - [x] `test_chunk_note_h3_is_split_point`
  - [x] `test_chunk_note_heading_context_no_hashes`
  - [x] `test_chunk_note_heading_not_in_body`
- [x] Verify all chunker tests fail (red check — `NoteChunker` does not exist yet)
- [x] Create `src/knowledge_garden/services/chunker.py` with `NoteChunker` class implementing `chunk_note`
- [x] Verify all chunker tests pass (green check)

---

## Step 3 — HuggingFace Embedder

### 3a — Config additions

- [x] Write test `test_config_hf_section_optional` in `tests/test_config.py` (red phase)
- [x] Write test `test_config_hf_env_token_override` in `tests/test_config.py` (red phase)
- [x] Write test `test_config_hf_env_token_merges` in `tests/test_config.py` (red phase)
- [x] Verify all three config tests fail (red check — `HuggingFaceConfig` and `Config.hugging_face` do not exist yet)
- [x] Add `HuggingFaceConfig` Pydantic model to `src/knowledge_garden/config.py`
- [x] Add `hugging_face: HuggingFaceConfig | None = None` field to `Config`
- [x] Add `HF_API_TOKEN` env var override block to `Config.from_yaml()` (after the existing `NEO4J_URI` block)
- [x] Verify all three config tests pass (green check)

### 3b — HuggingFace embedder

- [x] Write tests for `HuggingFaceEmbedder` in `tests/test_hf_embedder.py` (red phase)
  - [x] `test_hf_embed_single_text`
  - [x] `test_hf_embed_batch`
  - [x] `test_hf_embed_batching_splits_large_input`
  - [x] `test_hf_embed_empty_list`
  - [x] `test_hf_embed_api_error_propagates`
  - [x] `test_hf_dimension_returns_configured`
  - [x] `test_hf_close_closes_client`
- [x] Verify all embedder tests fail (red check — `HuggingFaceEmbedder` does not exist yet)
- [x] Create `src/knowledge_garden/services/hf_embedder.py` with `HuggingFaceEmbedder` implementing `EmbeddingService`
  - [x] `__init__` constructs `httpx.AsyncClient` with bearer auth header
  - [x] `embed` returns `[]` immediately for empty input
  - [x] `embed` batches by `_batch_size` and issues one POST per batch to `/models/{model}`
  - [x] `embed` calls `response.raise_for_status()` before reading body
  - [x] `embed` parses response as bare `list[list[float]]` (no wrapper key)
  - [x] `dimension` returns `self._dimension`
  - [x] `close` calls `await self._client.aclose()`
- [x] Verify all embedder tests pass (green check)

### 3c — Lifespan provider dispatch

- [x] Write tests for the lifespan dispatch in `tests/test_api.py` (red phase)
  - [x] `test_lifespan_selects_together_embedder`
  - [x] `test_lifespan_selects_hf_embedder`
  - [x] `test_lifespan_unknown_provider_raises`
- [x] Verify all dispatch tests fail (red check — dispatch logic does not exist yet)
- [x] Update `src/knowledge_garden/main.py`:
  - [x] Add `from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder` import
  - [x] Replace single `TogetherAIEmbedder(...)` call with the provider dispatch block (see contract section 3.3)
- [x] Verify all dispatch tests pass (green check)
- [x] Verify existing `test_health_endpoint` and `test_health_response_schema` tests still pass

---

## Step 4 — API Router Module

- [x] Create `src/knowledge_garden/api/__init__.py` (empty file)
- [x] Create `src/knowledge_garden/api/routes.py` with an empty `APIRouter` instance named `router` and the Pydantic schemas (`IngestRequest`, `IngestResponse`, `NoteSummary`, `NotesListResponse`)
- [x] Modify `src/knowledge_garden/main.py` to import and register the router:
  ```python
  from knowledge_garden.api.routes import router
  app.include_router(router, prefix="/api/v1")
  ```
- [x] Verify existing `test_health_endpoint` and `test_health_response_schema` tests still pass after the router registration change

---

## Step 5 — Ingest Endpoint

- [x] Add the `test_app` fixture (described in contract section 7.1) to `tests/test_ingest_api.py` or `tests/conftest.py`
- [x] Write tests for `POST /api/v1/ingest` in `tests/test_ingest_api.py` (red phase)
  - [x] `test_ingest_vault_not_found`
  - [x] `test_ingest_happy_path`
  - [x] `test_ingest_empty_vault`
  - [x] `test_ingest_calls_upsert_note`
  - [x] `test_ingest_calls_upsert_chunk`
  - [x] `test_ingest_calls_embedder`
  - [x] `test_ingest_embed_not_called_for_empty_vault`
  - [x] `test_ingest_response_schema`
- [x] Verify all ingest endpoint tests fail (red check — route handler does not exist yet)
- [x] Implement `ingest_vault` handler in `src/knowledge_garden/api/routes.py`
  - [x] Vault lookup with 404 on miss
  - [x] Parser call
  - [x] Chunker call (per note)
  - [x] Batch embed call (skip if no chunks)
  - [x] Assign embeddings back to chunks
  - [x] Upsert notes loop
  - [x] Upsert chunks loop
  - [x] Return `IngestResponse` with timing
- [x] Verify all ingest endpoint tests pass (green check)

---

## Step 6 — Notes Listing Endpoint

- [x] Write tests for `GET /api/v1/notes` in `tests/test_notes_api.py` (red phase)
  - [x] `test_list_notes_empty`
  - [x] `test_list_notes_returns_correct_count`
  - [x] `test_list_notes_schema`
  - [x] `test_list_notes_id_is_string`
  - [x] `test_list_notes_outgoing_links`
- [x] Verify all notes listing tests fail (red check — route handler does not exist yet)
- [x] Implement `list_notes` handler in `src/knowledge_garden/api/routes.py`
  - [x] Call `get_all_notes()` on graph store
  - [x] Convert `Note` objects to `NoteSummary`
  - [x] Return `NotesListResponse`
- [x] Verify all notes listing tests pass (green check)

---

## Final Verification

- [x] Run full test suite: `uv run pytest tests/ -v -m unit`
- [x] Confirm all new tests pass (98 total unit tests passing: 31 Phase 01 + 67 Phase 02)
- [x] Run linter: `uv run ruff check src/ tests/`
- [x] Run type checker: `uv run mypy src/`
- [x] Confirm `GET /api/v1/health` still passes (integration)
