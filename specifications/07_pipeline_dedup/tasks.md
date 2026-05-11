# 07 — Tasks

## Step 1: Configuration

- [ ] Write test: `DedupConfig` model has `threshold: float = 0.95`
- [ ] Write test: `BusinessConfig` has `dedup: DedupConfig` field
- [ ] Write test: YAML with `dedup.threshold: 0.8` loads correctly
- [ ] Verify tests fail (red)
- [ ] Add `DedupConfig` to `config.py`
- [ ] Add `dedup` field to `BusinessConfig`
- [ ] Add `dedup.threshold` to `config.yaml`
- [ ] Verify tests pass (green)

## Step 2: IngestPhase and IngestResult

- [ ] Write test: `IngestResult` has `chunks_skipped: int` field
- [ ] Write test: `IngestPhase` has CHUNKING, DEDUP, UPSERT values
- [ ] Verify tests fail (red)
- [ ] Update `IngestPhase` enum: remove EMBEDDING/INDEXING, add DEDUP/UPSERT
- [ ] Add `chunks_skipped` to `IngestResult`
- [ ] Verify tests pass (green)

## Step 3: Pipeline flow refactor

- [ ] Write test: pipeline with all-new chunks → dedup returns no matches → all chunks upserted, `chunks_skipped == 0`
- [ ] Write test: pipeline with duplicate chunks → `find_similar_chunks` returns match → chunk skipped, `chunks_skipped == 1`
- [ ] Write test: pipeline with mixed batch → some duplicates, some novel → correct counts
- [ ] Write test: dedup threshold passed from constructor to `find_similar_chunks`
- [ ] Write test: `upsert_note` called once per note even when chunks span multiple batches
- [ ] Write test: `find_similar_chunks` exception → chunk treated as novel (fail open)
- [ ] Write test: all chunks in batch are duplicates → note still upserted, no chunks upserted
- [ ] Update all existing pipeline tests for new flow (DEDUP/UPSERT phases, per-batch embed+upsert)
- [ ] Verify all tests fail (red)
- [ ] Implement new pipeline flow in `pipeline.py`
- [ ] Verify all tests pass (green)

## Step 4: CLI updates

- [ ] Write test: CLI passes `dedup_threshold` from config to pipeline
- [ ] Update `_run_ingest` progress bars: DEDUP + UPSERT instead of EMBEDDING + INDEXING
- [ ] Update result table: add `Chunks skipped` row
- [ ] Verify tests pass

## Step 5: Final verification

- [ ] Run `ruff check` on all modified files
- [ ] Run `mypy` on all modified files
- [ ] Run full unit test suite
