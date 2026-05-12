# 14 — HF Inference Provider Pin (mini-spec / paper trail)

**Status:** quick patch landed; full SDD ceremony deferred.

## Problem

Calling `search_notes` (MCP tool) against the HF-backed embedder raised:

```
RuntimeError: coroutine raised StopIteration
```

Traceback originated in `huggingface_hub` 1.12.0:

```
File ".../huggingface_hub/inference/_providers/__init__.py", line 256, in get_provider_helper
    provider = next(iter(provider_mapping)).provider
               ~~~~^^^^^^^^^^^^^^^^^^^^^^^^
StopIteration
```

For `intfloat/multilingual-e5-large-instruct` the SDK's per-model provider
mapping is empty, so `next(iter(...))` raises `StopIteration`, which PEP 479
converts to `RuntimeError` when it leaks out of an `async def`.

Same code path is used by the FastAPI `/search` route, so the bug is not
MCP-specific — any caller of `HuggingFaceEmbedder.embed` hits it.

## Fix

Pin the legacy HF Inference provider on client construction so the
per-model mapping lookup is bypassed:

```python
self._client = AsyncInferenceClient(
    token=hf_config.api_key,
    provider="hf-inference",
    timeout=120.0,
)
```

Verified manually: `feature_extraction("hello world", model="intfloat/multilingual-e5-large-instruct")`
returns a 1024-dim `np.ndarray` (matches `EmbeddingConfig.dimension`).

## Scope of change

- `src/knowledge_garden/services/hf_embedder.py` — one-line addition to
  `AsyncInferenceClient(...)` kwargs.
- `tests/test_hf_embedder.py` — added `test_hf_client_pins_hf_inference_provider`
  which patches `AsyncInferenceClient` and asserts `provider="hf-inference"`
  is passed.

## Why a mini-spec instead of full ceremony

Spec 05 (`05_hf_sdk_embedder/contract.md`) defines the `AsyncInferenceClient`
constructor call, so strictly this is an amendment that warrants a new
numbered spec with intent/roadmap/contract/tasks/audit. Skipped here because:

1. The change is one keyword argument, fully covered by one new unit test.
2. The user needs working semantic search now (existing notes are already
   embedded with e5-large-instruct; switching providers would invalidate the
   index).
3. Embedding output is unchanged — `provider="hf-inference"` routes to the
   same HF Inference endpoint the SDK would have selected before the per-model
   mapping was introduced.

## Follow-up (deferred)

Promote to a proper spec (`14_hf_provider_pin/{intent,roadmap,contract,tasks,audit}.md`)
when convenient. The contract clause to lock in:

> `HuggingFaceEmbedder.__init__` MUST construct `AsyncInferenceClient` with
> `provider="hf-inference"`. Rationale: the SDK's default per-model provider
> mapping is empty for several embedding models including
> `intfloat/multilingual-e5-large-instruct`, causing
> `StopIteration` → `RuntimeError: coroutine raised StopIteration`.
