# Contract: HF Embedder Integration Tests

**STATUS: FROZEN**

Amends: `specifications/05_hf_sdk_embedder/contract.md` — adds integration tests, fixes timeout, fixes ndarray shape handling.

---

## 1. File Locations

| File | Change |
|------|--------|
| `tests/test_hf_embedder_integration.py` | New file — integration tests calling real HuggingFace API |
| `src/knowledge_garden/services/hf_embedder.py` | Fix timeout, fix 1D/2D shape handling |

---

## 2. Integration Test Specifications

File: `tests/test_hf_embedder_integration.py`

All tests are `@pytest.mark.integration`. All tests call the real HuggingFace serverless API. All tests skip automatically when `HF_API_TOKEN` is not set in the environment.

### 2.1 Fixtures

```python
import os

import numpy as np
import pytest

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder

HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
SKIP_REASON = "HF_API_TOKEN not set — skipping real API test"

DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct"
DEFAULT_DIMENSION = 1024
DEFAULT_BATCH_SIZE = 8


@pytest.fixture
def hf_config() -> HuggingFaceConfig:
    return HuggingFaceConfig(api_key=HF_API_TOKEN)


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        model=DEFAULT_MODEL,
        dimension=DEFAULT_DIMENSION,
        batch_size=DEFAULT_BATCH_SIZE,
    )


@pytest.fixture
def embedder(hf_config, embedding_config) -> HuggingFaceEmbedder:
    return HuggingFaceEmbedder(hf_config, embedding_config)
```

### 2.2 Test Cases

| Test name | Marker | Description | Input | Expected output | Edge cases |
|-----------|--------|-------------|-------|-----------------|------------|
| `test_hf_embed_single_text_real` | integration | Real API call with 1 text → 1 vector of correct dimension | `["Knowledge garden integration test."]` | `len(result) == 1`, `len(result[0]) == 1024` | — |
| `test_hf_embed_batch_produces_independent_vectors` | integration | 3 distinct texts → 3 vectors that are NOT identical | `["cat", "dog", "automobile"]` | 3 vectors, each dimension 1024, cosine sim between "cat" and "automobile" < 0.95 | Confirms API does NOT concatenate |
| `test_hf_embed_batch_vs_individual_match` | integration | Single call with list vs individual calls produce same vectors | `["hello world"]` batch + `["hello world"]` individual | Cosine similarity between batch result and individual result >= 0.999 | Output consistency |
| `test_hf_embed_dimension_matches_config` | integration | `dimension()` returns config value | — | `1024` | — |
| `test_hf_embed_empty_list_real` | integration | `[]` → no API call, returns `[]` | `[]` | `[]` | — |

### 2.3 Test Implementation Details

- `test_hf_embed_single_text_real`: Call `await embedder.embed(["Knowledge garden integration test."])`. Assert 1 vector of 1024 floats. Close embedder in `finally`.
- `test_hf_embed_batch_produces_independent_vectors`: Call `await embedder.embed(["cat", "dog", "automobile"])`. Assert 3 vectors. Compute cosine similarity between result[0] ("cat") and result[2] ("automobile") — assert it's less than 0.95 (they should be semantically different, not concatenated).
- `test_hf_embed_batch_vs_individual_match`: Call batch with `["hello world"]`, then call individually with `["hello world"]` (separate embedder instance or same). Compare first vector from batch with the individual vector — cosine similarity should be >= 0.999 (near-identical).
- `test_hf_embed_dimension_matches_config`: No API call needed. Assert `embedder.dimension() == 1024`.
- `test_hf_embed_empty_list_real`: Call `await embedder.embed([])`. Assert `result == []`.

---

## 3. Embedder Fixes

File: `src/knowledge_garden/services/hf_embedder.py`

### 3.1 Timeout Increase

Change `timeout=30.0` to `timeout=120.0` in the `AsyncInferenceClient` constructor.

The 30-second timeout caused `httpx.ReadTimeout` during real ingestion with the free serverless API, which can take 60-90+ seconds for large batches under load.

### 3.2 1D vs 2D ndarray Shape Handling

When `feature_extraction` is called with a **single string**, it returns a 1D ndarray of shape `(dim,)`. When called with a **list of strings**, it returns a 2D ndarray of shape `(N, dim)`. The current code calls `.tolist()` on both, which produces `list[float]` for 1D and `list[list[float]]` for 2D. This means `all_embeddings.extend()` would get individual floats from a 1D result instead of vectors.

Since we always pass a list (even for a single text), the result should always be 2D. However, as a safety measure, the implementation should normalize the output to always be 2D before calling `.tolist()`.

Updated `embed()` method logic:

```python
ndarray: np.ndarray = await self._client.feature_extraction(  # type: ignore[arg-type]
    chunk, model=model
)
if ndarray.ndim == 1:
    ndarray = ndarray.reshape(1, -1)
all_embeddings.extend(ndarray.tolist())
```

This ensures that even if the SDK returns a 1D array for a single-element list, we reshape it to `(1, dim)` before converting.

### 3.3 Updated Unit Test

The existing unit test `test_hf_embed_single_text` in `tests/test_hf_embedder.py` should be updated to mock a 1D return (to verify the reshape logic works):

```python
async def test_hf_embed_single_text_1d_reshaped(self, hf_config):
    """Edge case: feature_extraction returns 1D ndarray for single text → reshaped to 2D."""
    config = EmbeddingConfig(model="test-model", dimension=384, batch_size=64)
    embedder = HuggingFaceEmbedder(hf_config, config)
    mock_ndarray = np.array([0.1] * 384)  # 1D shape (384,)
    with _patch_fe(embedder) as mock_fe:
        mock_fe.return_value = mock_ndarray
        result = await embedder.embed(["hello"])
    assert result == [[0.1] * 384]
```

---

## 4. What Does NOT Change

- `EmbeddingService` ABC — unchanged
- `TogetherAIEmbedder` — unchanged
- `cli.py`, `main.py` — unchanged
- `config.py` — unchanged
- Existing unit tests in `test_hf_embedder.py` remain (with one new test added)
- `pyproject.toml` — unchanged
