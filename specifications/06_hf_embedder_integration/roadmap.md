# Roadmap: HF Embedder Integration Tests

## Step 1 — Write integration tests

Write `tests/test_hf_embedder_integration.py` with tests that call the real HuggingFace API. Tests skip automatically when `HF_API_TOKEN` is not set. Cover: single text, batch list produces independent vectors, 1D vs 2D shape handling, dimension matches config.

**Done when:** Integration test file exists; tests skip when token absent; tests pass when token present.

## Step 2 — Fix embedder for shape correctness and timeout

Update `HuggingFaceEmbedder.embed()` to handle the fact that `feature_extraction` returns a 1D ndarray `(dim,)` for single strings and a 2D ndarray `(N, dim)` for lists. Also increase timeout from 30s to 120s.

**Done when:** Unit tests pass; integration tests pass against real API.

## Step 3 — Verify end-to-end

Run `uv run pytest tests/ -v` and confirm both unit and integration tests pass.

**Done when:** Full suite green.
