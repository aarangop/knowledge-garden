# Contract: HF SDK Embedder

**STATUS: FROZEN**

Amends: `specifications/04_config_split/contract.md` — removes `hf_base_url` from `AppSettings`, removes `base_url` from `HuggingFaceConfig`, updates `hugging_face` property.
Supersedes: `specifications/02_ingestion/contract.md` section 3 — replaces the `httpx`-based `HuggingFaceEmbedder` with an `AsyncInferenceClient`-based implementation.

---

## 1. File Locations

| File | Change |
|------|--------|
| `pyproject.toml` | Add `huggingface_hub[inference]>=1.0.0` to dependencies |
| `src/knowledge_garden/config.py` | Remove `hf_base_url` from `AppSettings`, remove `base_url` from `HuggingFaceConfig`, update `hugging_face` property |
| `src/knowledge_garden/services/hf_embedder.py` | Full rewrite using `AsyncInferenceClient` |
| `tests/test_hf_embedder.py` | Full rewrite (mock `AsyncInferenceClient.feature_extraction` instead of `httpx.post`) |
| `.env.example` | Remove `HF_BASE_URL` line |

---

## 2. Dependency Addition

File: `pyproject.toml`

Add to `dependencies` list:

```
"huggingface_hub[inference]>=1.0.0",
```

---

## 3. Config Changes

File: `src/knowledge_garden/config.py`

### 3.1 HuggingFaceConfig

The `base_url` field is removed. The new model:

```python
class HuggingFaceConfig(BaseModel):
    api_key: str = ""
```

### 3.2 AppSettings

The `hf_base_url` field is removed. Relevant fields of the updated `AppSettings`:

```python
class AppSettings(BaseSettings):
    # ... other fields unchanged ...

    # HuggingFace (optional)
    hf_api_token: str | None = None
    # hf_base_url is REMOVED — the SDK handles routing

    # ... other fields unchanged ...
```

### 3.3 hugging_face Property

The computed property no longer passes `base_url`:

```python
@property
def hugging_face(self) -> HuggingFaceConfig | None:
    if self.hf_api_token is None:
        return None
    return HuggingFaceConfig(
        api_key=self.hf_api_token,
    )
```

### 3.4 .env.example

Remove the `HF_BASE_URL` line. The HuggingFace section becomes:

```
# Optional (HuggingFace — only needed if embedding.provider = huggingface)
HF_API_TOKEN=
```

### 3.5 Backward Compatibility

`AppSettings` already has `extra="ignore"` in its `model_config`. Old `.env` files that still contain `HF_BASE_URL=...` will not raise an error — the value is silently ignored.

---

## 4. HuggingFaceEmbedder Rewrite

File: `src/knowledge_garden/services/hf_embedder.py`

### 4.1 Class Definition

```python
import numpy as np
from huggingface_hub import AsyncInferenceClient

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.embedder import EmbeddingService


class HuggingFaceEmbedder(EmbeddingService):
    """Embedding via HuggingFace Inference API using the SDK client.

    Uses AsyncInferenceClient.feature_extraction() with batch inputs.
    The HF Inference API accepts string[] as inputs for feature-extraction,
    returning one embedding vector per input string. The SDK's type
    signature currently shows text: str but passing a list works correctly
    and is endorsed as safe by the HuggingFace team
    (see github.com/huggingface/huggingface_hub/issues/2824).
    """

    def __init__(self, hf_config: HuggingFaceConfig, embedding_config: EmbeddingConfig) -> None:
        self._client = AsyncInferenceClient(
            token=hf_config.api_key,
            timeout=30.0,
        )
        self._embedding_config = embedding_config

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via feature_extraction. Batches internally.

        Returns [] immediately for empty input without making any API calls.
        Splits texts into batch_size chunks and calls feature_extraction
        once per chunk, passing the list of strings. Converts each
        np.ndarray row to list[float].

        Parameters
        ----------
        texts:
            List of strings to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in input order.

        Raises
        ------
        Exception
            Any exception raised by AsyncInferenceClient.feature_extraction
            (e.g., huggingface_hub.errors.HttpError) propagates to the caller.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = self._embedding_config.batch_size
        model = self._embedding_config.model

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            ndarray: np.ndarray = await self._client.feature_extraction(  # type: ignore[arg-type]
                chunk, model=model
            )
            all_embeddings.extend(ndarray.tolist())

        return all_embeddings

    def dimension(self) -> int:
        """Return the configured embedding dimension."""
        return self._embedding_config.dimension

    async def close(self) -> None:
        """Close the underlying AsyncInferenceClient."""
        await self._client.close()
```

### 4.2 Key Behavioral Details

- `feature_extraction` accepts **either a single string or a list of strings** as its `text` parameter. The API returns one embedding vector per input string. Passing a list is officially supported by the Inference API and is endorsed as safe by the HuggingFace team (github.com/huggingface/huggingface_hub/issues/2824), even though the SDK type signature currently shows `text: str`.
- The `# type: ignore[arg-type]` comment suppresses the mypy warning for passing a list. This will be unnecessary once the SDK adds `List[str]` to its type signature.
- Texts are split into `batch_size` chunks. Each chunk results in **one API call** passing the full list of strings. This is more efficient than per-text calls.
- `feature_extraction` returns `np.ndarray` with shape `(N, dim)` when given N strings. The implementation calls `.tolist()` to convert to `list[list[float]]`.
- `close()` delegates to `AsyncInferenceClient.close()`.

### 4.3 Constructor Signature

Unchanged from the `02_ingestion` spec:

```python
def __init__(self, hf_config: HuggingFaceConfig, embedding_config: EmbeddingConfig) -> None
```

This means `cli.py` and `main.py` require **no changes** — they already call `HuggingFaceEmbedder(hf, embedding_config)` where `hf` is a `HuggingFaceConfig` (now without `base_url`).

---

## 5. What Does NOT Change

- `EmbeddingService` ABC (`src/knowledge_garden/services/embedder.py`) — unchanged
- `TogetherAIEmbedder` — unchanged
- `TogetherAIConfig` — unchanged
- `Neo4jConfig` — unchanged
- `EmbeddingConfig` defaults (model, dimension, batch_size) — unchanged
- `cli.py` — no changes (constructor call remains valid)
- `main.py` — no changes (constructor call remains valid)
- `BusinessConfig` and its sub-models — unchanged
- `src/knowledge_garden/services/neo4j_store.py` — unchanged
- `src/knowledge_garden/api/` — unchanged
- `src/knowledge_garden/models/` — unchanged

---

## 6. Test Specifications

### 6.1 HuggingFaceEmbedder Tests

File: `tests/test_hf_embedder.py`

All tests are `@pytest.mark.unit`. Full rewrite — the old `httpx`-based tests are replaced.

**Mocking strategy:** Mock `AsyncInferenceClient.feature_extraction` to return `np.ndarray` objects. Use `unittest.mock.AsyncMock` with `patch.object` on the embedder's `_client`. The mock receives a list of strings and returns an ndarray of shape `(N, dim)`.

**Fixtures:**

```python
import numpy as np
from unittest.mock import AsyncMock, patch

import pytest

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder


@pytest.fixture
def hf_config() -> HuggingFaceConfig:
    """HuggingFaceConfig with a test token (no base_url)."""
    return HuggingFaceConfig(api_key="test-token")


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """EmbeddingConfig pointing at a small sentence-transformer model."""
    return EmbeddingConfig(
        model="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
        batch_size=64,
    )


@pytest.fixture
def embedder(hf_config, embedding_config) -> HuggingFaceEmbedder:
    """Constructed HuggingFaceEmbedder ready for patching."""
    return HuggingFaceEmbedder(hf_config, embedding_config)
```

**Test cases:**

| Test name | Marker | Description | Input | Expected output | Edge cases |
|-----------|--------|-------------|-------|-----------------|------------|
| `test_hf_embed_single_text` | unit | Mock `feature_extraction` returning 2D ndarray `(1, 384)` → 1 vector | `["hello"]` | `[[0.1]*384]` | — |
| `test_hf_embed_batch` | unit | 3 texts in one call → `feature_extraction` called once with list, returns `(3, 384)` | `["a","b","c"]` | 3 vectors | Single API call for batch |
| `test_hf_embed_batching_splits_large_input` | unit | 100 texts, batch_size=64 → 2 `feature_extraction` calls (64 then 36) | 100 texts | 100 vectors, 2 calls | Batch splitting |
| `test_hf_embed_empty_list` | unit | `[]` → no calls, returns `[]` | `[]` | `[]` | Empty input |
| `test_hf_embed_api_error_propagates` | unit | `feature_extraction` raises exception → error propagates | texts | raises same exception | API error |
| `test_hf_dimension_returns_configured` | unit | `dimension()` returns config value | — | 384 | — |
| `test_hf_close_closes_client` | unit | `close()` works without error | — | no error | Cleanup |

**Test implementation details:**

- `test_hf_embed_single_text`: Patch `embedder._client.feature_extraction` with `AsyncMock(return_value=np.array([[0.1] * 384]))` (2D shape `(1, 384)`). Call `embed(["hello"])`. Assert `result == [[0.1] * 384]`. Verify `feature_extraction` called once with first positional arg `["hello"]` and `model=<config_model>`.

- `test_hf_embed_batch`: Patch `feature_extraction` to return `np.array([[0.1]*384, [0.2]*384, [0.3]*384])` (shape `(3, 384)`). Call `embed(["a","b","c"])`. Assert `len(result) == 3` and each vector has 384 elements. Verify `feature_extraction` called once with `["a","b","c"]`.

- `test_hf_embed_batching_splits_large_input`: Create embedder with `batch_size=64`. Patch `feature_extraction` with `AsyncMock(side_effect=[np.array([[0.1]*384]*64), np.array([[0.1]*384]*36)])`. Call `embed(["x"]*100)`. Assert `feature_extraction.call_count == 2`. Assert `len(result) == 100`. Verify first call received 64 texts and second received 36.

- `test_hf_embed_empty_list`: Patch `feature_extraction` with `AsyncMock()`. Call `embed([])`. Assert `result == []`. Assert `feature_extraction.assert_not_called()`.

- `test_hf_embed_api_error_propagates`: Patch `feature_extraction` with `AsyncMock(side_effect=RuntimeError("API error"))`. Call `embed(["text"])`. Assert `pytest.raises(RuntimeError)`.

- `test_hf_dimension_returns_configured`: No mocking needed. Assert `embedder.dimension() == 384`.

- `test_hf_close_closes_client`: Patch `embedder._client.close` with `AsyncMock()`. Call `await embedder.close()`. Assert `embedder._client.close` called once.

### 6.2 Config Change Tests

File: `tests/test_config.py` (existing file, modifications only)

#### 6.2.1 New tests for HuggingFaceConfig and AppSettings

| Test name | Marker | Description | Inputs | Expected output | Edge cases |
|-----------|--------|-------------|--------|-----------------|------------|
| `test_hugging_face_config_no_base_url` | unit | `HuggingFaceConfig` model has no `base_url` field | `HuggingFaceConfig(api_key="k")` | `set(HuggingFaceConfig.model_fields.keys()) == {"api_key"}` | Field removed |
| `test_app_settings_hf_base_url_ignored` | unit | `HF_BASE_URL` set in env → silently ignored (no `hf_base_url` attribute) | `TOGETHER_API_KEY=k`, `HF_BASE_URL=https://custom.co` in env | `not hasattr(settings, "hf_base_url")` | Backward compat |
| `test_app_settings_hugging_face_property_no_base_url` | unit | `settings.hugging_face` returns `HuggingFaceConfig` without `base_url` | `TOGETHER_API_KEY=k`, `HF_API_TOKEN=tok` | `not hasattr(settings.hugging_face, "base_url")` | Property update |

#### 6.2.2 Updates to existing TestAppSettings tests (from spec 04)

These existing tests must be modified to remove `base_url`/`hf_base_url` references:

- **`test_app_settings_hf_optional`** — remove any assertion checking `hf_base_url` or `base_url`. Test should only verify `hf_api_token` is populated.
- **`test_app_settings_hf_absent`** — unchanged (this test only checks `hf_api_token is None`).
- **`test_app_settings_hugging_face_property_set`** — remove any assertion checking `settings.hugging_face.base_url`. Only verify `settings.hugging_face.api_key`.
- **`test_app_settings_hugging_face_property_none`** — unchanged (this test only checks `hugging_face is None`).

---

## 7. Dependencies and Assumptions

- **New dependency:** `huggingface_hub[inference]>=1.0.0` provides `AsyncInferenceClient` and its `feature_extraction()` method.
- **`numpy`** is a transitive dependency of `huggingface_hub` (required for `np.ndarray` return type). It is not added explicitly to `pyproject.toml`.
- **`httpx`** remains a project dependency (used by `TogetherAIEmbedder`). It is simply no longer imported by `hf_embedder.py`.
- The `AsyncInferenceClient` constructor accepts `token` and `timeout` keyword arguments. The `token` is the HF API token (same value as `hf_config.api_key`). The `timeout` is a float in seconds.
- `AsyncInferenceClient.feature_extraction()` accepts **either a single string or a list of strings** as its `text` parameter. The Inference API officially supports `string[]` as `inputs` (documented at https://huggingface.co/docs/inference-providers/tasks/feature-extraction). The SDK type signature currently shows `text: str` but passing a list works correctly and is endorsed as safe by the HuggingFace team (github.com/huggingface/huggingface_hub/issues/2824). A `# type: ignore[arg-type]` comment suppresses the mypy warning until the SDK updates its type signature.
- When given a list of N strings, `feature_extraction` returns `np.ndarray` with shape `(N, dim)`. Calling `.tolist()` on this produces `list[list[float]]`.
- `AsyncInferenceClient.close()` is an async method that cleans up the client's HTTP session.
- The constructor signature `HuggingFaceEmbedder(hf_config, embedding_config)` is preserved exactly, so `cli.py` and `main.py` need no changes.
- `HuggingFaceConfig` with `base_url` removed still satisfies existing callers — `hf_embedder.py` no longer reads `base_url`, and the `hugging_face` property on `AppSettings` no longer passes it.
