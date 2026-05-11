# 08 — Contract

## 1. GraphStore extension

### `get_all_chunks`

New abstract method on `GraphStore`:

```python
@abstractmethod
async def get_all_chunks(self) -> list[Chunk]:
    """Return all Chunk nodes that have embeddings, ordered by note_id then index."""
    ...
```

Neo4j implementation:

```cypher
MATCH (c:Chunk)
WHERE c.embedding IS NOT NULL
RETURN c
ORDER BY c.note_id, c.index
```

## 2. SemanticLinker

New service: `services/linker.py`

### Constructor

```python
class SemanticLinker:
    def __init__(
        self,
        graph_store: GraphStore,
        threshold: float = 0.7,
        max_neighbors: int = 20,
    ) -> None:
```

### `link_all`

```python
async def link_all(
    self,
    progress_callback: ProgressCallback | None = None,
) -> LinkResult:
```

**Algorithm:**

1. Fetch all chunks with embeddings via `graph_store.get_all_chunks()`
2. For each chunk:
   a. Query `graph_store.find_similar_chunks(embedding=chunk.embedding, limit=max_neighbors, threshold=threshold)`
   b. Filter out matches where `match.note_id == chunk.note_id` (same-note exclusion)
   c. For each surviving match, call `graph_store.create_similarity(chunk.id, match.id, score)`
3. Track stats: `chunks_processed`, `similarity_edges_created`

Progress callback for this phase:
- `(LinkPhase.SIMILAR, current, total, f"{edges} edges")`

**Idempotency:** `create_similarity` uses MERGE — re-running is safe.

**Batch size:** Process chunks in batches of `batch_size` (constructor param, default 100) for memory efficiency. The batch size here controls how many chunks are fetched/processed at once, not embedding API calls (embeddings already exist).

### `derive_note_relationships`

```python
async def derive_note_relationships(
    self,
    progress_callback: ProgressCallback | None = None,
) -> int:
```

**Algorithm:**

1. Fetch all notes via `graph_store.get_all_notes()`
2. For each note:
   a. Get chunks via `graph_store.get_chunks_for_note(note.id)`
   b. For each chunk, query `graph_store.get_note_relationships` won't work — need to traverse SIMILAR_TO edges
   c. Actually: use a Cypher query to aggregate SIMILAR_TO into RELATED_TO
3. Return count of RELATED_TO edges created

**Better approach:** Single Cypher query to derive all RELATED_TO at once:

```cypher
MATCH (n1:Note)-[:HAS_CHUNK]->(c1:Chunk)-[s:SIMILAR_TO]->(c2:Chunk)<-[:HAS_CHUNK]-(n2:Note)
WHERE n1 <> n2 AND s.score >= $threshold
WITH n1, n2, max(s.score) AS best_score
MERGE (n1)-[r:RELATED_TO]->(n2)
SET r.score = best_score
RETURN count(r) AS edges_created
```

This is more efficient than iterating per-note. Add a `derive_related_to` method to GraphStore that runs this query.

### LinkPhase

```python
class LinkPhase(StrEnum):
    SIMILAR = "similar"
    RELATED = "related"
```

### LinkResult

```python
@dataclass
class LinkResult:
    chunks_processed: int
    similarity_edges_created: int
    note_relationships_derived: int
    duration_seconds: float
```

## 3. GraphStore: `derive_related_to`

New method on `GraphStore`:

```python
@abstractmethod
async def derive_related_to(self, threshold: float = 0.7) -> int:
    """Derive RELATED_TO edges from SIMILAR_TO chunk edges.
    
    For each pair of Notes whose chunks have SIMILAR_TO edges above threshold,
    create a RELATED_TO edge with score = max chunk similarity.
    
    Returns the number of RELATED_TO edges created.
    """
    ...
```

Neo4j implementation uses the Cypher query above.

## 4. CLI: `kg link` command

```python
@app.command()
def link(config_path: str = typer.Option("config.yaml", "--config")) -> None:
```

- Load settings and business config
- Create embedder + graph_store (same as ingest)
- Initialize graph_store
- Create `SemanticLinker(graph_store, threshold=business.linking.threshold, max_neighbors=business.linking.max_neighbors)`
- Run `linker.link_all(progress_callback=...)` then `linker.derive_note_relationships(progress_callback=...)`
- Display Rich progress bars (SIMILAR phase, RELATED phase)
- Print result table with chunks processed, similarity edges, note relationships, duration
- Close graph_store

## 5. API: `POST /api/v1/link`

New endpoint in `api/routes.py` or new `api/link.py`:

```python
@router.post("/api/v1/link")
async def link_knowledge(request: Request) -> dict:
```

- Get graph_store from `request.app.state`
- Run linker + derive
- Return `LinkResult` as dict

## 6. Test specifications

### Unit tests (`tests/test_linker.py`)

| Test | Description |
|------|-------------|
| `test_linker_link_all_creates_similarity_edges` | Mock `get_all_chunks` returns 2 chunks from different notes, `find_similar_chunks` returns a match → `create_similarity` called |
| `test_linker_link_all_excludes_same_note` | Mock returns 2 chunks from same note, `find_similar_chunks` returns match from same note → `create_similarity` NOT called |
| `test_linker_link_all_no_matches` | `find_similar_chunks` returns empty → no edges created |
| `test_linker_link_all_respects_threshold` | Verify `find_similar_chunks` called with `threshold` from constructor |
| `test_linker_link_all_respects_max_neighbors` | Verify `find_similar_chunks` called with `limit=max_neighbors` |
| `test_linker_link_all_idempotent` | Running twice with same data → same result (MERGE semantics) |
| `test_linker_link_all_progress_callback` | Verify LinkPhase.SIMILAR callbacks emitted |
| `test_linker_derive_calls_graph_store` | Verify `derive_related_to` called with correct threshold |
| `test_linker_derive_progress_callback` | Verify LinkPhase.RELATED callbacks emitted |
| `test_linker_result_shape` | LinkResult has correct fields and values |

### Integration tests

| Test | Description |
|------|-------------|
| `test_linker_integration_creates_edges` | Ingest 2 notes, run linker, verify SIMILAR_TO and RELATED_TO edges in Neo4j |

### Existing tests to update

- `tests/test_config.py` — verify `LinkingConfig` defaults (already exists, no change needed)

## 7. Edge cases

- Chunks with `embedding=None` — skipped by `get_all_chunks` (WHERE c.embedding IS NOT NULL)
- Zero chunks in the graph — linker returns `chunks_processed=0, similarity_edges_created=0`
- All chunks from the same note — no SIMILAR_TO edges (same-note exclusion)
- `find_similar_chunks` raises exception — treat as "no matches" (fail open), log warning
- Very similar threshold (0.99) — only near-identical chunks linked (useful for dedup, but dedup is already handled)

## 8. Dependencies and assumptions

- Chunks already have embeddings stored in Neo4j (from ingestion pipeline)
- Neo4j vector index `chunk_embeddings` exists and is populated
- `find_similar_chunks` works correctly (tested in prior specs)
- `create_similarity` and `create_link` are implemented and idempotent (MERGE)
- `LinkingConfig` with `threshold` and `max_neighbors` exists on `BusinessConfig`
- Deduplication already handled at ingestion time (spec 07, threshold 0.95)
