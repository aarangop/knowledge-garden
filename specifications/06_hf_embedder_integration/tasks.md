# Tasks: HF Embedder Integration Tests

## Integration tests (TDD — write first)

- [ ] Create `tests/test_hf_embedder_integration.py` with fixtures (skip if no HF_API_TOKEN)
- [ ] Write `test_hf_embed_single_text_real` — real API call, 1 vector of correct dimension
- [ ] Write `test_hf_embed_batch_produces_independent_vectors` — 3 texts produce 3 different vectors (not concatenated)
- [ ] Write `test_hf_embed_batch_vs_individual_match` — batch and individual calls produce same vector
- [ ] Write `test_hf_embed_dimension_matches_config` — dimension() returns config value
- [ ] Write `test_hf_embed_empty_list_real` — empty input returns empty list
- [ ] Verify integration tests skip when `HF_API_TOKEN` not set: `uv run pytest tests/test_hf_embedder_integration.py -v`

## Embedder fixes (green phase)

- [ ] Increase `AsyncInferenceClient` timeout from 30.0 to 120.0 in `hf_embedder.py`
- [ ] Add 1D→2D reshape safety in `embed()`: if `ndarray.ndim == 1`, reshape to `(1, -1)`
- [ ] Add unit test `test_hf_embed_single_text_1d_reshaped` to `tests/test_hf_embedder.py`
- [ ] Verify all unit tests pass: `uv run pytest tests/test_hf_embedder.py tests/test_config.py -v -m unit`

## Verification

- [ ] Run integration tests with `HF_API_TOKEN` set: `uv run pytest tests/test_hf_embedder_integration.py -v -m integration`
- [ ] Run full unit test suite: `uv run pytest tests/ -v -m unit`
- [ ] Run `ruff check src/knowledge_garden/services/hf_embedder.py`
- [ ] Run `mypy src/knowledge_garden/services/hf_embedder.py`
