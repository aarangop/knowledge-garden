# 07 — Roadmap

## Step 1: Add dedup configuration to BusinessConfig

Add `dedup_threshold: float = 0.95` to the ingestion/pipeline config section so the semantic dedup threshold is configurable.

**Done when:** `BusinessConfig` has a `dedup_threshold` field, YAML config loads it, existing tests still pass.

## Step 2: Refactor IngestPhase and pipeline flow

Replace current EMBEDDING + INDEXING phases with DEDUP + UPSERT. In the new flow, each batch is: embed → dedup (using embeddings just computed) → upsert surviving chunks + their parent notes.

**Done when:** Pipeline processes chunks per-batch through embed→dedup→upsert, progress callback reports DEDUP and UPSERT phases, all existing tests updated and passing.

## Step 3: Update CLI progress display

Update Rich progress bars to show DEDUP and UPSERT phases instead of EMBEDDING and INDEXING.

**Done when:** `kg ingest` shows DEDUP and UPSERT progress bars.

## Step 4: Add IngestResult fields for dedup tracking

Add `chunks_skipped: int` to `IngestResult` so the user knows how many chunks were deduped.

**Done when:** `IngestResult` has `chunks_skipped`, pipeline populates it, CLI displays it.
