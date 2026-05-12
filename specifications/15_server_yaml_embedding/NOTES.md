# 15 — Server-side YAML embedding config (mini-spec / paper trail)

**Status:** quick patch landed; full SDD ceremony deferred.

## Problem

The FastAPI server (`main.py`) and the MCP server (`mcp_server.py`) both
instantiated `EmbeddingConfig()` with **defaults** at startup:

```python
embedding_config = EmbeddingConfig()  # provider=together, model=m2-bert, dim=768
```

But the CLI (which performs ingestion) loads `BusinessConfig.from_yaml("config.yaml")`
and uses `business.embedding`, which in this repo is:

```yaml
embedding:
  provider: huggingface
  model: intfloat/multilingual-e5-large-instruct
  dimension: 1024
```

Consequence: chunks were stored in Neo4j as 1024-dim e5 vectors during
ingestion, but the server would embed queries with a different model
(Together's 768-dim `m2-bert-80M-8k-retrieval`, or — with `HF_API_TOKEN` set —
ask HF Inference to feature-extract a *Together-owned* model, which HF rejects
with "doesn't support task 'feature-extraction'").

Net effect: `/api/v1/search` and the MCP `search_notes` tool would never
return useful results, despite the index being fine and the embedder being
fine in isolation.

The pre-existing comment in `main.py` ("Use default EmbeddingConfig for the
server; provider selection is determined by whether hf_api_token is present
— see spec 04_config_split section 4") records the original spec-04 decision,
which this patch overrides.

## Fix

Make the server lifespans load `BusinessConfig.from_yaml("config.yaml")` and
use `business.embedding`. Dispatch embedder provider on
`business.embedding.provider`, matching the CLI's logic in
`cli.py::_make_embedder`:

```python
business = BusinessConfig.from_yaml("config.yaml")
embedding_config = business.embedding

graph_store = Neo4jGraphStore(settings.neo4j, embedding_config)
await graph_store.initialize()

provider = embedding_config.provider
if provider == "huggingface":
    hf = settings.hugging_face
    if hf is None:
        raise ValueError("HF_API_TOKEN is required when embedding.provider is 'huggingface'")
    embedder = HuggingFaceEmbedder(hf, embedding_config)
elif provider == "together":
    embedder = TogetherAIEmbedder(settings.together_ai, embedding_config)
else:
    raise ValueError(f"Unknown embedding provider: {provider!r}")
```

Verified end-to-end against the live Neo4j vault: `find_similar_chunks`
returns real hits with scores ~0.9 for the query "philosophy of language".

## Scope of change

- `src/knowledge_garden/mcp_server.py` — `kg_lifespan` loads YAML and
  dispatches by provider.
- `src/knowledge_garden/main.py` — `lifespan` same change.
- `tests/test_mcp_server.py` — new `TestLifespanLoadsYamlEmbeddingConfig`
  test asserts the lifespan reads `config.yaml` and passes the YAML-loaded
  `EmbeddingConfig` to both `Neo4jGraphStore` and the embedder.
- `tests/test_api.py` — existing health / lifespan-dispatch tests updated
  to patch `BusinessConfig.from_yaml` and assert dispatch by
  `business.embedding.provider` instead of `settings.hugging_face`. The
  test class docstring and one test name were updated to reflect the new
  dispatch axis.

## Why a mini-spec instead of full ceremony

Spec 04 (`04_config_split`) explicitly decided that the FastAPI server
would NOT load `BusinessConfig` and would use `EmbeddingConfig()` defaults.
Spec 12 (MCP server) inherited that decision. This patch reverses it for
both servers. Strictly, that warrants a new numbered spec amending both
spec 04 and spec 12 with intent/roadmap/contract/tasks/audit. Skipped here
because:

1. The change is mechanical (mirrors `cli.py::_make_embedder`).
2. The original spec-04 decision is demonstrably broken for any real
   deployment: dim/model mismatches silently destroy search recall.
3. The user needs working semantic search now.

## Follow-up (deferred)

Promote to a proper spec when convenient. The contract clauses to lock in:

- Both `lifespan` (FastAPI) and `kg_lifespan` (MCP) MUST load
  `BusinessConfig.from_yaml("config.yaml")` and use `business.embedding`
  for both `Neo4jGraphStore` and the embedder.
- Embedder dispatch is by `business.embedding.provider` (`"together"` |
  `"huggingface"`), not by the presence of `settings.hugging_face`.
- When `provider == "huggingface"` and `settings.hugging_face is None`,
  raise `ValueError` at startup.
- Update spec 04 section 4 (or supersede it) to record the reversal and
  the rationale.

The config path is currently hardcoded to `config.yaml` (relative to cwd).
A future spec may want to make this an env var (`KG_CONFIG_PATH`) for
deployments that don't run from the repo root.
