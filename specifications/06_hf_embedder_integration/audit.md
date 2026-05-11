# Audit: 06_hf_embedder_integration

**Spec:** specifications/06_hf_embedder_integration/
**Date:** 2026-05-09
**Verdict:** PASS WITH NOTES

---

## Contract Alignment

| Contract Item | Status | Notes |
|---|---|---|
| `tests/test_hf_embedder_integration.py` new file created | ✅ Implemented | File exists at correct path |
| `src/knowledge_garden/services/hf_embedder.py` timeout changed from 30.0 to 120.0 | ✅ Implemented | Line 26: `timeout=120.0` in `AsyncInferenceClient` constructor |
| 1D ndarray reshape safety: `if ndarray.ndim == 1: ndarray = ndarray.reshape(1, -1)` | ✅ Implemented | Lines 66-67 in `hf_embedder.py`, exact logic from contract |
| `all_embeddings.extend(ndarray.tolist())` after reshape | ✅ Implemented | Line 68 in `hf_embedder.py` |
| `HuggingFaceConfig` fixture in integration tests | ✅ Implemented | `hf_config` fixture at line 26 of integration test file |
| `EmbeddingConfig` fixture with correct defaults (model, dimension=1024, batch_size=8) | ✅ Implemented | `embedding_config` fixture at line 32, matches contract spec exactly |
| `HuggingFaceEmbedder` fixture in integration tests | ✅ Implemented | `embedder` fixture at line 39 |
| Skip guard: all integration tests skip when `HF_API_TOKEN` not set | ✅ Implemented | All 5 tests have `@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)` |
| All integration tests marked `@pytest.mark.integration` | ✅ Implemented | All 5 tests carry the marker |
| `DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct"` | ✅ Implemented | Line 16 |
| `DEFAULT_DIMENSION = 1024` | ✅ Implemented | Line 17 |
| `DEFAULT_BATCH_SIZE = 8` | ✅ Implemented | Line 18 |
| `EmbeddingService` ABC unchanged | ✅ Implemented | Contract item 4 — not modified |
| `TogetherAIEmbedder` unchanged | ✅ Implemented | Contract item 4 — not modified |
| `config.py` unchanged | ✅ Implemented | Contract item 4 — not modified |
| Existing unit tests in `test_hf_embedder.py` remain intact | ✅ Implemented | All 7 original tests still present and passing |
| New unit test `test_hf_embed_single_text_1d_reshaped` added to `test_hf_embedder.py` | ✅ Implemented | Lines 119-130 in `test_hf_embedder.py` |

---

## Test Coverage

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_hf_embed_single_text_real` | ✅ | ✅ (skipped — no token) | Correct skip behaviour; logic matches contract §2.3 |
| `test_hf_embed_batch_produces_independent_vectors` | ✅ | ✅ (skipped — no token) | Cosine similarity check `< 0.95` matches contract |
| `test_hf_embed_batch_vs_individual_match` | ✅ | ✅ (skipped — no token) | Cosine similarity check `>= 0.999` matches contract |
| `test_hf_embed_dimension_matches_config` | ✅ | ✅ (skipped — no token) | Synchronous, no `@pytest.mark.asyncio` — acceptable, no API call needed |
| `test_hf_embed_empty_list_real` | ✅ | ✅ (skipped — no token) | Uses `embedder` fixture but does not call `.close()` — see Deviations |
| `test_hf_embed_single_text_1d_reshaped` (unit) | ✅ | ✅ | 1D array `(384,)` mocked; result correctly asserted as `[[0.1]*384]` |

---

## Edge Cases

| Edge Case | Covered | Notes |
|---|---|---|
| 1D ndarray from `feature_extraction` (single string) | ✅ | `test_hf_embed_single_text_1d_reshaped` mocks a `(384,)` array and asserts reshape to `[[...]]` |
| Empty list — no API call | ✅ | Both unit (`test_hf_embed_empty_list`) and integration (`test_hf_embed_empty_list_real`) cover this |
| Batch of exactly one text returns list of one vector with correct length | ✅ | `test_hf_embed_single_text_real` asserts `len(result) == 1` and `len(result[0]) == 1024` |
| Independent vectors for semantically different inputs | ✅ | `test_hf_embed_batch_produces_independent_vectors` uses cosine-similarity guard |
| Determinism / output consistency (batch vs individual) | ✅ | `test_hf_embed_batch_vs_individual_match` covers this |

---

## Deviations

1. **`test_hf_embed_empty_list_real` missing `embedder.close()`**: The contract (§2.3) does not explicitly require a `finally` / `close()` call for this particular test. However, the other async tests that make real API calls all call `await embedder.close()`. Since `embed([])` makes no API call, the omission is harmless, but it is inconsistent with the pattern established in the other tests. Flag: minor, no impact on correctness.

2. **`test_hf_embed_dimension_matches_config` has no `@pytest.mark.asyncio`**: The contract description (§2.2) notes "No API call needed" for this test. The implementation is a plain synchronous `def` rather than `async def`, which is the correct choice and matches the contract's intent. No deviation in substance; just noting the implementation took the synchronous path the contract implied.

3. **`test_hf_embed_single_text_1d_reshaped` is not wrapped in the existing `TestHuggingFaceEmbedder` class**: The contract snippet (§3.3) presents the test as a standalone method, implying it could be either inside or outside the class. The implementation places it inside `TestHuggingFaceEmbedder` (lines 119-130 of `test_hf_embedder.py`), which is better organisation. This is a backward-compatible improvement.

---

## Observations

- The `test_hf_embed_single_text_1d_reshaped` implementation uses `"test-model"` as the model name (rather than the fixture's `"sentence-transformers/all-MiniLM-L6-v2"`). This is consistent with the contract snippet and is correct — the test is exercising reshape logic, not model identity.
- The integration test file includes `from __future__ import annotations` (line 7), which the contract boilerplate does not show. This is a harmless style addition.
- The `HF_API_TOKEN` module-level read (`os.environ.get("HF_API_TOKEN")`) at import time correctly supports `pytest.mark.skipif`, which evaluates at collection time. This is the correct pattern.
- All 8 unit tests pass; all 5 integration tests skip cleanly with the correct reason string. The total collected item count (13) matches expectations.

---

## Verdict Rationale

All contract items are implemented correctly. Every specified test exists and either passes (unit tests) or skips cleanly with the correct reason (integration tests, no `HF_API_TOKEN` in CI). The three deviations noted above are minor style/pattern observations that do not affect correctness, completeness, or backward compatibility. The verdict is **PASS WITH NOTES** rather than PASS solely because of the missing `close()` in `test_hf_embed_empty_list_real` (harmless) and the class-placement of the new unit test (an improvement). Neither item requires correction.
