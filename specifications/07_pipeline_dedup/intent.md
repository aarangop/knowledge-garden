# 07 — Pipeline Dedup and Atomic Upsert

Amends: 03_cli (pipeline progress), 02_ingestion (pipeline flow)

## Problem

The current pipeline embeds all chunks in bulk, then indexes all chunks in bulk. This has two issues:

1. **Wasted money on interruption.** If embedding completes but the CLI crashes or is interrupted before indexing, all embedding API costs are lost — those vectors are never persisted.
2. **Wasted money on re-ingestion.** Running `kg ingest` a second time on the same vault re-embeds and re-indexes every chunk, even if semantically identical chunks already exist in the graph.

## Desired behavior

- After chunking, the pipeline should **deduplicate** new chunks against the existing index using semantic similarity (cosine > 0.95), skipping chunks that already mean the same thing.
- Embedding and indexing should happen **per-batch** as a single atomic unit: embed a batch → dedup against index → upsert surviving chunks. If the process is interrupted, already-indexed batches are safe.
- The progress callback should report three phases: CHUNKING, DEDUP, UPSERT.

## Outcome

Running `kg ingest` twice on the same vault skips all chunks the second time (they're already indexed). Interrupting mid-ingest preserves all work done in completed batches.
