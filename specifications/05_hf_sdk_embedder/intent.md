# Intent: HF SDK Embedder

Amends: `04_config_split` (removes `base_url`/`hf_base_url` fields). Supersedes: `02_ingestion` section 3 (HuggingFaceEmbedder definition).

The HuggingFace embedder currently uses raw `httpx` calls against the Inference API. This works but forces us to manage HTTP concerns ourselves — retry logic, error parsing, endpoint routing, and response handling are all hand-rolled. The `huggingface_hub` SDK's `AsyncInferenceClient.feature_extraction()` already handles these concerns with built-in retries, proper error types, and automatic API routing.

Switching to the SDK gives us robustness for free and removes the need for a configurable `base_url`. The SDK knows where to route requests; if a user needs a custom endpoint they specify it via the model URL, not a base URL override. This lets us delete `base_url` from `HuggingFaceConfig` and `hf_base_url` from `AppSettings`, simplifying the config surface. Existing `.env` files that still contain `HF_BASE_URL` are harmless because `AppSettings` already has `extra="ignore"`.

The embedder's public interface — constructor signature, `embed()`, `dimension()`, `close()` — stays identical. Callers in `cli.py` and `main.py` require no changes. Internally, batching sends a list of strings per API call — the HF Inference API officially supports `string[]` as inputs for feature-extraction, and the SDK's `feature_extraction` method handles this correctly even though its type signature currently shows `text: str`. The HuggingFace team has endorsed this usage as safe and future-proof (github.com/huggingface/huggingface_hub/issues/2824).

Success looks like: `HuggingFaceEmbedder` uses `AsyncInferenceClient` under the hood, the `base_url` config fields are gone, all existing tests pass with updated mocks, and `httpx` is no longer imported by `hf_embedder.py`.
