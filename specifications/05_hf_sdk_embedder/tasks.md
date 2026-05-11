# Tasks: HF SDK Embedder

## Config changes (TDD)

- [ ] Write test `test_hugging_face_config_no_base_url` — verify `HuggingFaceConfig` has no `base_url` field
- [ ] Write test `test_app_settings_hf_base_url_ignored` — verify `HF_BASE_URL` in env is silently ignored
- [ ] Write test `test_app_settings_hugging_face_property_no_base_url` — verify `settings.hugging_face` has no `base_url`
- [ ] Verify all new config tests fail (red phase)
- [ ] Remove `hf_base_url` field from `AppSettings` in `config.py`
- [ ] Remove `base_url` field from `HuggingFaceConfig` in `config.py`
- [ ] Update `AppSettings.hugging_face` property to not pass `base_url`
- [ ] Update existing `test_app_settings_hf_optional` to remove `hf_base_url`/`base_url` assertions
- [ ] Update existing `test_app_settings_hugging_face_property_set` to remove `base_url` assertion
- [ ] Verify all config tests pass (green phase)
- [ ] Remove `HF_BASE_URL` line from `.env.example`

## HuggingFaceEmbedder rewrite (TDD)

- [ ] Write test `test_hf_embed_single_text` — mock `feature_extraction` returning 2D ndarray `(1, dim)` → 1 vector
- [ ] Write test `test_hf_embed_batch` — 3 texts in one call → `feature_extraction` called once with list → 3 vectors
- [ ] Write test `test_hf_embed_batching_splits_large_input` — 100 texts, batch_size=64 → 2 API calls
- [ ] Write test `test_hf_embed_empty_list` — `[]` → no calls, returns `[]`
- [ ] Write test `test_hf_embed_api_error_propagates` — `feature_extraction` raises → error propagates
- [ ] Write test `test_hf_dimension_returns_configured` — `dimension()` returns config value
- [ ] Write test `test_hf_close_closes_client` — `close()` delegates to client
- [ ] Write test `test_hf_dimension_returns_configured` — `dimension()` returns config value
- [ ] Write test `test_hf_close_closes_client` — `close()` delegates to client
- [ ] Verify all new embedder tests fail (red phase)
- [ ] Add `huggingface_hub[inference]>=1.0.0` to `pyproject.toml` dependencies
- [ ] Run `uv sync` to install the new dependency
- [ ] Rewrite `HuggingFaceEmbedder` using `AsyncInferenceClient` — implement `__init__`, `embed` (batch list inputs, one API call per chunk), `dimension`, `close`
- [ ] Remove `httpx` import from `hf_embedder.py`
- [ ] Verify all embedder tests pass (green phase)

## Cleanup and verification

- [ ] Run `ruff check src/knowledge_garden/services/hf_embedder.py src/knowledge_garden/config.py`
- [ ] Run `mypy src/knowledge_garden/services/hf_embedder.py src/knowledge_garden/config.py`
- [ ] Run full test suite `pytest` — all tests pass
