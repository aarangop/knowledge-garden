# Audit: HF SDK Embedder

**Spec:** specifications/05_hf_sdk_embedder/
**Date:** 2026-04-27
**Verdict:** PASS WITH NOTES

## Contract Alignment

| Contract Item | Status | Notes |
|---|---|---|
| §2: Add `huggingface_hub[inference]>=1.0.0` to pyproject.toml | ✅ Implemented | Present at `pyproject.toml:19` |
| §2: `numpy` not added explicitly to pyproject.toml | ⚠️ Deviation | `numpy>=2.0.0` added at `pyproject.toml:20`. Contract §7 states "It is not added explicitly to `pyproject.toml`". Justified: `numpy` is needed at runtime for `np.ndarray` and `huggingface_hub` does not bundle it as a required dependency. |
| §3.1: HuggingFaceConfig has only `api_key` | ✅ Implemented | `config.py:50-51` — `class HuggingFaceConfig(BaseModel): api_key: str = ""` |
| §3.2: `hf_base_url` removed from AppSettings | ✅ Implemented | No `hf_base_url` field in `AppSettings` (`config.py:59-93`) |
| §3.3: `hugging_face` property does not pass `base_url` | ✅ Implemented | `config.py:111-117` — returns `HuggingFaceConfig(api_key=self.hf_api_token)` |
| §3.4: `HF_BASE_URL` removed from .env.example | ✅ Implemented | `.env.example:15-16` — only `HF_API_TOKEN=` remains |
| §3.5: Backward compat via `extra="ignore"` | ✅ Implemented | `config.py:68` — `extra="ignore"` in model_config |
| §4.1: Class inherits from EmbeddingService | ✅ Implemented | `hf_embedder.py:15` |
| §4.1: Imports (`numpy`, `AsyncInferenceClient`) | ✅ Implemented | `hf_embedder.py:8-9` |
| §4.1: Constructor signature | ✅ Implemented | `hf_embedder.py:23` — `__init__(self, hf_config, embedding_config) -> None` |
| §4.1: `AsyncInferenceClient(token=..., timeout=30.0)` | ✅ Implemented | `hf_embedder.py:24-27` |
| §4.1: `embed()` method signature and return type | ✅ Implemented | `hf_embedder.py:30` — `async def embed(self, texts: list[str]) -> list[list[float]]` |
| §4.1: `embed()` docstring | ⚠️ Deviation | Contract specifies a detailed docstring with Parameters/Returns/Raises sections. Implementation has no docstring on `embed()`. |
| §4.1: Empty input early return | ✅ Implemented | `hf_embedder.py:31-32` |
| §4.1: Batch splitting logic | ✅ Implemented | `hf_embedder.py:38-43` |
| §4.1: Passes list to `feature_extraction` | ✅ Implemented | `hf_embedder.py:42` — `chunk` passed as first positional arg |
| §4.1: `# type: ignore[arg-type]` on feature_extraction | ✅ Implemented | `hf_embedder.py:42` |
| §4.1: `ndarray.tolist()` conversion | ✅ Implemented | `hf_embedder.py:43` |
| §4.1: `dimension()` returns configured value | ✅ Implemented | `hf_embedder.py:47-48` |
| §4.1: `close()` delegates to client | ✅ Implemented | `hf_embedder.py:50-51` |
| §4.1: Class docstring | ⚠️ Deviation | Contract specifies 8-line docstring mentioning SDK type signature and HuggingFace team endorsement. Implementation has 5-line docstring omitting those details. |
| §4.1: `close()` has no extra type ignore | ⚠️ Deviation | `hf_embedder.py:51` has `# type: ignore[no-untyped-call]` not specified in contract. Needed for mypy strict mode but deviates from contract's exact code. |
| §4.2: Key behavioral details (all bullets) | ✅ Implemented | All 5 bullet points verified against `hf_embedder.py` |
| §4.3: Constructor signature unchanged | ✅ Implemented | Matches `HuggingFaceEmbedder(hf_config, embedding_config)` |
| §5: No changes to cli.py, main.py, etc. | ⚠️ Deviation | Source files unchanged, but `test_api.py:133` has stale `mock_hf_config.base_url = "https://api-inference.huggingface.co"`. Not a source change, but a test remnant referencing the removed field. |

## Test Coverage

| Specified Test | Present | Passing | Notes |
|---|---|---|---|
| `test_hf_embed_single_text` | ✅ | ✅ | `test_hf_embedder.py:41` |
| `test_hf_embed_batch` | ✅ | ✅ | `test_hf_embedder.py:56` |
| `test_hf_embed_batching_splits_large_input` | ✅ | ✅ | `test_hf_embedder.py:70` |
| `test_hf_embed_empty_list` | ✅ | ✅ | `test_hf_embedder.py:92` |
| `test_hf_embed_api_error_propagates` | ✅ | ✅ | `test_hf_embedder.py:101` |
| `test_hf_dimension_returns_configured` | ✅ | ✅ | `test_hf_embedder.py:108` |
| `test_hf_close_closes_client` | ✅ | ✅ | `test_hf_embedder.py:113` |
| `test_hugging_face_config_no_base_url` | ✅ | ✅ | `test_config.py:334` |
| `test_app_settings_hf_base_url_ignored` | ✅ | ✅ | `test_config.py:83` |
| `test_app_settings_hugging_face_property_no_base_url` | ❌ (merged) | ✅ | Contract specifies a distinct test with this name. Implementation merged its assertions into existing `test_app_settings_hugging_face_property_set` (`test_config.py:132-141`). Edge case IS covered (`not hasattr(settings.hugging_face, "base_url")` at line 141), but test name and structure deviate. |

### Existing Test Updates (§6.2.2)

| Test | Updated Correctly | Notes |
|---|---|---|
| `test_app_settings_hf_optional` | ✅ | `test_config.py:72-80` — no `base_url` references, checks `hf_api_token` and `not hasattr(settings, "hf_base_url")` |
| `test_app_settings_hf_absent` | ✅ | `test_config.py:93-100` — unchanged as specified |
| `test_app_settings_hugging_face_property_set` | ✅ | `test_config.py:132-141` — checks `api_key`, no `base_url` assertion |
| `test_app_settings_hugging_face_property_none` | ✅ | `test_config.py:122-129` — unchanged as specified |

## Edge Cases

| Edge Case | Covered | Notes |
|---|---|---|
| Empty input → `[]` without API call | ✅ | `test_hf_embed_empty_list` |
| API error propagates to caller | ✅ | `test_hf_embed_api_error_propagates` |
| Batch splitting (100 texts / batch_size 64) | ✅ | `test_hf_embed_batching_splits_large_input` — verifies 2 calls (64 + 36) |
| `HF_BASE_URL` in env silently ignored | ✅ | `test_app_settings_hf_base_url_ignored` |
| `HuggingFaceConfig` has no `base_url` field | ✅ | `test_hugging_face_config_no_base_url` |
| `hugging_face` property returns config without `base_url` | ✅ | Merged into `test_app_settings_hugging_face_property_set` |

## Deviations

1. **`numpy>=2.0.0` added to pyproject.toml** (`pyproject.toml:20`) — Contract §7 states numpy "is not added explicitly to `pyproject.toml`". The implementation adds it because `huggingface_hub` does not bundle numpy as a required dependency, yet the code directly imports and uses `np.ndarray` at runtime. This is a practical necessity; without it, `uv run` in a clean environment would fail at `import numpy as np` in `hf_embedder.py:8`.

2. **Missing `embed()` docstring** (`hf_embedder.py:30`) — Contract specifies a detailed docstring with Parameters, Returns, and Raises sections. The implementation has no docstring on `embed()`.

3. **Shorter class docstring** (`hf_embedder.py:16-21`) — Contract specifies an 8-line docstring mentioning the SDK type signature quirk and HuggingFace team endorsement (github issue #2824). Implementation has a 5-line docstring omitting those details. The comment on line 41 references the issue, but the class docstring does not.

4. **Extra `# type: ignore[no-untyped-call]` on `close()`** (`hf_embedder.py:51`) — Not specified in contract. Required for mypy strict mode compliance since `AsyncInferenceClient.close()` lacks type stubs.

5. **`test_app_settings_hugging_face_property_no_base_url` not a distinct test** — Contract §6.2.1 specifies a test named `test_app_settings_hugging_face_property_no_base_url`. Its assertions (`not hasattr(settings.hugging_face, "base_url")`) are instead included in the existing `test_app_settings_hugging_face_property_set` at `test_config.py:141`. Edge case is covered but test structure deviates.

6. **Stale `base_url` reference in `test_api.py:133`** — `mock_hf_config.base_url = "https://api-inference.huggingface.co"` sets a `base_url` attribute on a mock `HuggingFaceConfig`. Since `HuggingFaceConfig` no longer has `base_url`, this line is misleading dead code. It does not cause test failures because `MagicMock` accepts any attribute assignment.

## Observations

- All 143 unit tests pass (9 integration tests deselected).
- `AppSettings` has `model_config` defined twice (`config.py:64-69` and `config.py:88-93`). This is a pre-existing issue from a prior spec, not introduced by spec 05, but it's redundant and could cause confusion.
- The `test_config.py:36` `monkeypatch.delenv("HF_BASE_URL", raising=False)` call is appropriate — it ensures the env var is absent even if it was set in the host environment.

## Verdict Rationale

**PASS WITH NOTES** — All functional requirements are met: the embedder correctly uses `AsyncInferenceClient`, batching works, `base_url` is removed from config, backward compatibility is preserved, and all 143 unit tests pass. However, there are 6 deviations from the contract's exact specification. The most significant are: (1) `numpy` added explicitly to pyproject.toml contrary to contract §7, and (2) `test_app_settings_hugging_face_property_no_base_url` is not a distinct test as specified. The numpy deviation is pragmatically justified — the code would fail without it. The test structure deviation covers the same edge case but in a combined test. The remaining deviations (missing docstrings, extra type ignore, stale test_api.py reference) are minor. None of the deviations affect runtime correctness or test reliability.
