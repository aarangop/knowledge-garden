# 07 — Contract

## 1. Configuration

### DedupConfig

New Pydantic model in `config.py`:

```python
class DedupConfig(BaseModel):
    threshold: float = 0.95
```

Add `dedup: DedupConfig = DedupConfig()` to `BusinessConfig`.

YAML key: `dedup.threshold`. Default 0.95.

## 2. IngestPhase

Replace current `IngestPhase` values:

```python
class IngestPhase(StrEnum):
    CHUNKING = "chunking"
    DEDUP = "dedup"
    UPSERT = "upsert"
```

## 3. IngestResult

Add field:

```python
@dataclass
class IngestResult:
    notes_parsed: int
    chunks_created: int
    chunks_skipped: int  # NEW: chunks that matched existing index at dedup threshold
    duration_seconds: float
```

## 4. IngestPipeline

### Constructor

```python
class IngestPipeline:
    def __init__(
        self,
        parser: MarkdownParser,
        chunker: NoteChunker,
        embedder: EmbeddingService,
        graph_store: GraphStore,
        embed_batch_size: int = 32,
        dedup_threshold: float = 0.95,
    ) -> None:
```

### Flow

```
1. CHUNKING phase (unchanged)
   - Parse vault, chunk each note
   - Progress callback: (CHUNKING, i, total_notes, note.title)

2. For each batch of chunks (size = embed_batch_size):
   a. Embed the batch
      - Call embedder.embed(batch_texts) → batch_vectors
      - Assign vectors to chunks

   b. DEDUP phase
      - For each chunk in batch, call graph_store.find_similar_chunks(
          embedding=chunk.embedding, limit=1, threshold=dedup_threshold
        )
      - If any result returned, mark chunk as duplicate (skip it)
      - Progress callback: (DEDUP, checked_count, total_chunks, f"{skipped} skipped")

   c. UPSERT phase
      - Upsert parent notes for new chunks (if not already upserted in this run)
      - Upsert each new chunk
      - Progress callback: (UPSERT, upserted_count, total_new_chunks, f"batch {batch_idx+1}/{num_batches}")
```

Notes upserted once: track which note IDs have been upserted in a `set[UUID]` during the run. Only call `upsert_note` the first time a note's chunk appears in a new batch.

### Empty vault

If `notes` is empty, no callbacks are fired (same as current behavior).

### No chunks

If chunking produces zero chunks, notes are still upserted (for metadata/links). DEDUP and UPSERT callbacks are not called.

## 5. ProgressCallback

```python
ProgressCallback = Callable[[IngestPhase, int, int, str], None]
```

Same signature as current, but phases are CHUNKING / DEDUP / UPSERT.

## 6. CLI

Update `_run_ingest` to:
- Pass `dedup_threshold=business.dedup.threshold` to IngestPipeline
- Show DEDUP and UPSERT progress bars instead of EMBEDDING and INDEXING
- Display `chunks_skipped` in the result table

## 7. Test specifications

### Unit tests (`tests/test_pipeline.py`)

All existing tests updated for new flow. New tests:

| Test | Description |
|------|-------------|
| `test_pipeline_dedup_skips_identical_chunks` | Mock `find_similar_chunks` to return a match for a chunk → that chunk is skipped, `chunks_skipped == 1` |
| `test_pipeline_dedup_keeps_novel_chunks` | Mock `find_similar_chunks` to return no matches → all chunks are upserted, `chunks_skipped == 0` |
| `test_pipeline_dedup_threshold_from_constructor` | Pipeline constructed with `dedup_threshold=0.9` → passes 0.9 to `find_similar_chunks` |
| `test_pipeline_upsert_note_called_once_per_note` | 2 batches from same note → `upsert_note` called once, `upsert_chunk` called per new chunk |
| `test_pipeline_chunks_skipped_zero_for_empty_index` | `find_similar_chunks` returns `[]` for all → `chunks_skipped == 0` |
| `test_pipeline_result_has_chunks_skipped` | IngestResult has `chunks_skipped` field |

### Existing tests to update

- All tests referencing `IngestPhase.EMBEDDING` or `IngestPhase.INDEXING` → use `IngestPhase.DEDUP` / `IngestPhase.UPSERT`
- All tests checking `embed` call patterns → update for per-batch flow
- `IngestResult` assertions → include `chunks_skipped`
- Progress callback tests → verify DEDUP and UPSERT phases

## 8. Edge cases

- Chunk with no embedding (shouldn't happen, but if `embed` returns fewer vectors than texts, that batch is skipped with a warning)
- `find_similar_chunks` raises an exception → treat as "not duplicate" (fail open) to avoid losing chunks
- All chunks in a batch are duplicates → note is still upserted, no chunks upserted for that batch
- Empty vault → no callbacks
- No chunks (chunking produces 0) → notes upserted, no DEDUP/UPSERT callbacks

## 9. Dependencies and assumptions

- `find_similar_chunks` exists on GraphStore ABC and Neo4jGraphStore implementation
- Chunks are embedded before dedup (embedding is needed for semantic search)
- The HNSW vector index in Neo4j is already populated for existing chunks
- Dedup threshold 0.95 is a reasonable default for near-duplicate detection (may need tuning)
