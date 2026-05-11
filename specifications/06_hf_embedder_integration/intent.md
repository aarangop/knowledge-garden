# Intent: HF Embedder Integration Tests

Amends: `05_hf_sdk_embedder` (adds integration tests, fixes timeout, validates batch correctness).

The HuggingFace embedder was implemented with only unit tests (mocked SDK calls). We need integration tests that call the real API to validate that:

1. The SDK's `feature_extraction` method correctly returns one independent embedding vector per input string when called with a list — confirming the API does not concatenate inputs.
2. The embedder works end-to-end with a real model on the serverless API.
3. The timeout is sufficient for the free serverless tier.

Additionally, the initial 30-second timeout caused `ReadTimeout` errors during real ingestion. The timeout must be increased, and the embedder should handle the 1D vs 2D ndarray shape difference that occurs when calling `feature_extraction` with a single string vs a list.

Success looks like: integration tests pass against the real HuggingFace API, batch embedding produces independent per-text vectors (not concatenated), and ingestion completes without timeout.
