# Roadmap: HF SDK Embedder

## Step 1 — Remove base_url from config models

Remove `base_url` from `HuggingFaceConfig` and `hf_base_url` from `AppSettings`. Update the `hugging_face` computed property on `AppSettings` to not pass `base_url`. Remove `HF_BASE_URL` from `.env.example`.

**Done when:** `HuggingFaceConfig` has only `api_key`; `AppSettings` has no `hf_base_url`; `.env.example` has no `HF_BASE_URL` line.

## Step 2 — Write failing tests for config changes

Write tests verifying: `HuggingFaceConfig` has no `base_url` field; `HF_BASE_URL` in env is silently ignored; `settings.hugging_face` returns object without `base_url`; existing `TestAppSettings` tests updated to remove `base_url` assertions.

**Done when:** All new config tests fail (red phase); existing tests referencing `base_url`/`hf_base_url` also fail.

## Step 3 — Implement config changes

Apply the model edits from Step 1. Update `.env.example`.

**Done when:** Config tests from Step 2 pass (green phase).

## Step 4 — Write failing tests for SDK-based HuggingFaceEmbedder

Rewrite `tests/test_hf_embedder.py` to mock `AsyncInferenceClient.feature_extraction` instead of `httpx.post`. The mock receives a list of strings and returns a 2D ndarray. Cover: single text, batch (single API call with list), batch splitting with large input, empty list, API error propagation, dimension, close.

**Done when:** All embedder tests fail (red phase) — `AsyncInferenceClient` does not exist in the implementation yet.

## Step 5 — Rewrite HuggingFaceEmbedder using AsyncInferenceClient

Replace `httpx.AsyncClient` with `huggingface_hub.AsyncInferenceClient`. Implement `embed()` using `feature_extraction` with batch list inputs (one API call per batch-size chunk). Convert `np.ndarray` returns to `list[list[float]]` via `.tolist()`. Implement `close()`.

**Done when:** All embedder tests pass (green phase).

## Step 6 — Add huggingface_hub dependency

Add `huggingface_hub[inference]>=1.0.0` to `pyproject.toml` dependencies. Run full test suite to confirm no regressions.

**Done when:** `pyproject.toml` lists the new dependency; `uv sync` succeeds; all tests pass.

## Step 7 — Refactor and verify

Clean up any dead imports (`httpx` in `hf_embedder.py`). Run linter and type checker. Verify full suite passes.

**Done when:** `ruff` and `mypy` report no errors; full test suite green.
