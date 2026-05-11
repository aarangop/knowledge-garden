# 10 — Contract

## 1. Service-layer `SearchResult` dataclass

New dataclass in `services/graph_store.py` (defined in the same file as `GraphStore`, before the class definition):

```python
from dataclasses import dataclass

@dataclass
class SearchResult:
    note_id: str          # str(UUID) of the parent Note
    title: str
    source_vault: str
    original_path: str
    score: float          # highest chunk similarity score for this note
    snippet: str          # chunk.content[:200] of the best-matching chunk
    heading_context: str  # chunk.heading_context of the best-matching chunk
```

This is a plain dataclass (not a Pydantic model). It is the return type of `GraphStore.search_notes` and `Neo4jGraphStore.search_notes`. The API route maps it into the `SearchResult` Pydantic response model (section 5).

## 2. GraphStore extension: `get_note_by_id`

New abstract method on `GraphStore` (in `services/graph_store.py`):

```python
@abstractmethod
async def get_note_by_id(self, note_id: object) -> Note | None:
    """Return the Note with the given id, or None if it does not exist.

    Args:
        note_id: The UUID of the note (UUID instance or str — coerced to str
                 via str(note_id) before the query).

    Returns:
        Note domain model, or None if no Note with that id exists.
    """
    ...
```

Neo4j implementation (in `services/neo4j_store.py`):

```cypher
MATCH (n:Note {id: $id}) RETURN n
```

Uses `await result.single()`. Returns `None` when `.single()` returns `None`. Reconstructs a `Note` from the node properties using the same pattern as `get_all_notes` (UUID coercion: `UUID(node["id"])`).

## 3. GraphStore extension: `get_stats`

New abstract method on `GraphStore` (in `services/graph_store.py`):

```python
@abstractmethod
async def get_stats(self) -> dict[str, int | list[str]]:
    """Return graph statistics.

    Returns a dict with exactly the following keys:
        "note_count"            -> int
        "chunk_count"           -> int
        "similarity_edge_count" -> int  (count of SIMILAR_TO edges)
        "related_to_edge_count" -> int  (count of RELATED_TO edges)
        "links_to_edge_count"   -> int  (count of LINKS_TO edges)
        "vault_names"           -> list[str]  (sorted alphabetically, distinct)
    """
    ...
```

Neo4j implementation uses five separate session.run calls (one per query — simpler to mock and maintain):

```cypher
-- query 1 (note_count + vault_names in one pass):
MATCH (n:Note) RETURN count(n) AS note_count, collect(DISTINCT n.vault) AS vault_names

-- query 2:
MATCH (c:Chunk) RETURN count(c) AS chunk_count

-- query 3:
MATCH ()-[s:SIMILAR_TO]->() RETURN count(s) AS similarity_edge_count

-- query 4:
MATCH ()-[r:RELATED_TO]->() RETURN count(r) AS related_to_edge_count

-- query 5:
MATCH ()-[l:LINKS_TO]->() RETURN count(l) AS links_to_edge_count
```

Implementation rules:
- Each query is run in a separate `async with self._driver.session(...) as session:` block (not within a single transaction).
- `vault_names` is sorted alphabetically (`sorted(...)`) before being returned.
- If the note query returns no record (empty graph), `note_count = 0` and `vault_names = []`.
- If any count query returns no record, treat the count as `0`.

## 4. GraphStore extension: `search_notes`

New abstract method on `GraphStore` (in `services/graph_store.py`):

```python
@abstractmethod
async def search_notes(
    self,
    query_embedding: list[float],
    limit: int = 10,
    vault_filter: str | None = None,
) -> list[SearchResult]:
    """Semantic search: find the most relevant notes for a query embedding.

    Algorithm:
    1. Call self.find_similar_chunks(
           embedding=query_embedding,
           limit=limit * 5,   # over-fetch to allow dedup; see note below
           threshold=0.0,
       ) -> raw_pairs: list[tuple[Chunk, float]]
       Threshold is 0.0 here; callers who want a threshold should pre-filter
       or the API layer filters post-search. The limit multiplier of 5 is a
       fixed over-fetch factor to ensure enough unique notes are available
       after deduplication.
    2. Deduplicate by note: for each (chunk, score) pair, keep only the
       highest-scoring chunk per note_id. Build a dict[UUID, (Chunk, float)]
       using `best[chunk.note_id] = (chunk, score)` when
       score > best[chunk.note_id][1] (or note not yet seen).
    3. Fetch the parent Note for each unique note_id via get_note_by_id.
       Skip any chunk whose parent Note cannot be found (orphaned chunk).
    4. If vault_filter is not None, drop results where note.vault != vault_filter.
    5. Sort surviving (chunk, score, note) triples by score descending.
    6. Take the first `limit` entries.
    7. Build a SearchResult for each:
         note_id=str(note.id),
         title=note.title,
         source_vault=note.vault,
         original_path=note.original_path,
         score=score,
         snippet=chunk.content[:200],
         heading_context=chunk.heading_context,
    8. Return list[SearchResult].

    Args:
        query_embedding: Pre-computed embedding vector for the query.
        limit: Maximum number of SearchResult objects to return (default 10, max 50).
        vault_filter: If not None, only return notes from this vault.

    Returns:
        list[SearchResult] sorted by score descending, length <= limit.
    """
    ...
```

Implementation note: the over-fetch factor of 5 (`limit * 5`) is hardcoded in the Neo4j implementation. It compensates for deduplication removing multiple chunks from the same note. If the graph has fewer than `limit * 5` chunks total, `find_similar_chunks` returns whatever is available.

## 5. Configuration: `search_limit` added to `BusinessConfig`

Add one field to `SearchConfig` — a new sub-model of `BusinessConfig`:

```python
class SearchConfig(BaseModel):
    search_limit: int = 10
```

Add `search: SearchConfig = SearchConfig()` to `BusinessConfig`:

```python
class BusinessConfig(BaseModel):
    vaults: list[VaultConfig] = []
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    linking: LinkingConfig = LinkingConfig()
    dedup: DedupConfig = DedupConfig()
    export: ExportConfig = ExportConfig()
    search: SearchConfig = SearchConfig()    # NEW
```

`SearchConfig` is added to `__all__` in `config.py`.

YAML representation (example, in `config.yaml`):
```yaml
search:
  search_limit: 20
```

## 6. API Pydantic models (in `api/routes.py`)

### `SearchResult` (API response model — distinct from the service-layer dataclass)

```python
class SearchResult(BaseModel):
    note_id: str
    title: str
    source_vault: str
    original_path: str
    score: float
    snippet: str          # chunk.content[:200]
    heading_context: str
```

### `SearchResponse`

```python
class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int            # len(results) after vault filter and limit applied
```

### `StatsResponse`

```python
class StatsResponse(BaseModel):
    note_count: int
    chunk_count: int
    similarity_edge_count: int
    related_to_edge_count: int
    links_to_edge_count: int
    vault_names: list[str]
```

Naming note: the API `SearchResult` Pydantic model and the service-layer `SearchResult` dataclass share a name but live in different modules. The route handler imports the service-layer dataclass as `ServiceSearchResult` to avoid collision:

```python
from knowledge_garden.services.graph_store import SearchResult as ServiceSearchResult
```

Alternatively, the route file may define the Pydantic model under the name `NoteSearchResult` to avoid any import aliasing. Either approach is acceptable to the executor; the API response field names (`note_id`, `title`, etc.) must match the spec exactly regardless of internal naming.

## 7. API endpoint: `GET /api/v1/search`

New route in `api/routes.py`:

```python
@router.get("/search")
async def search_notes(
    request: Request,
    q: str,
    limit: int = Query(default=10, ge=1, le=50),
    vault: str | None = Query(default=None),
) -> SearchResponse:
    """Semantic search over the knowledge graph.

    Algorithm:
    1. Embed q via request.app.state.embedder.embed([q]).
       Take the first element: vector: list[float].
    2. Call graph_store.search_notes(
           query_embedding=vector,
           limit=limit,
           vault_filter=vault,
       ) -> service_results: list[ServiceSearchResult]
    3. Map each ServiceSearchResult to the API SearchResult Pydantic model.
    4. Return SearchResponse(results=results, query=q, total=len(results)).
    """
```

Required import in routes.py: `from fastapi import Query`.

Error cases:
- Missing `q` parameter: FastAPI returns HTTP 422 automatically (required query parameter).
- `limit` outside 1–50: HTTP 422 (Pydantic/FastAPI validation).
- Empty results: HTTP 200 with `results=[], total=0`.
- `embedder` or `graph_store` unavailable (lifespan failed): HTTP 503 (pre-existing pattern, not handled specially here).

## 8. API endpoint: `GET /api/v1/stats`

New route in `api/routes.py`:

```python
@router.get("/stats")
async def get_graph_stats(request: Request) -> StatsResponse:
    """Return graph statistics.

    Calls graph_store.get_stats() and maps the result to StatsResponse.
    """
    graph_store = request.app.state.graph_store
    stats = await graph_store.get_stats()
    return StatsResponse(
        note_count=stats["note_count"],
        chunk_count=stats["chunk_count"],
        similarity_edge_count=stats["similarity_edge_count"],
        related_to_edge_count=stats["related_to_edge_count"],
        links_to_edge_count=stats["links_to_edge_count"],
        vault_names=stats["vault_names"],
    )
```

Error cases:
- `graph_store` unavailable: HTTP 503 (pre-existing lifespan error).
- Empty graph: HTTP 200 with all counts at 0 and `vault_names=[]`.

## 9. CLI: `kg search` command

Internal coroutine in `cli.py`:

```python
async def _run_search(
    embedder: EmbeddingService,
    graph_store: GraphStore,
    query: str,
    limit: int,
    threshold: float,
    vault: str | None,
) -> list[SearchResult]:
    """Embed query, search for similar notes via graph_store.search_notes.

    Closes both graph_store (and embedder via its close() method) in the
    finally block, mirroring the lifespan teardown order in main.py.

    Returns list[SearchResult] (service-layer dataclass) from graph_store.search_notes,
    already sorted by score descending.
    """
    await graph_store.initialize()
    try:
        vectors = await embedder.embed([query])
        vector = vectors[0]
        return await graph_store.search_notes(
            query_embedding=vector,
            limit=limit,
            vault_filter=vault,
        )
    finally:
        await embedder.close()
        await graph_store.close()
```

Note: `threshold` is accepted as a parameter for forward compatibility and is not currently forwarded to `search_notes` (which uses `threshold=0.0` internally). It is reserved for a future spec that threads threshold into `search_notes`.

Command signature:

```python
@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return"),
    threshold: float = typer.Option(0.7, "--threshold", help="Minimum similarity score (reserved, not yet applied)"),
    vault: str | None = typer.Option(None, "--vault", help="Filter by source vault name"),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
```

Command behavior:
1. Load `AppSettings` (exit 1 on exception, same pattern as `link` and `export` commands).
2. Load `BusinessConfig` from `config_path` (exit 1 on `FileNotFoundError`).
3. Build `effective_limit = limit if limit != 10 else business.search.search_limit` — if the user did not override `--limit`, use the config default.
4. Create `embedder` via `_make_embedder(settings, business)` (exit 1 on `ValueError`).
5. Create `graph_store` via `_make_graph_store(settings, business)`.
6. Run `results = asyncio.run(_run_search(embedder, graph_store, query, effective_limit, threshold, vault))`.
7. If `results` is empty: `typer.echo("No results found.")` and return (exit 0).
8. Otherwise: print a Rich `Table` with these columns in order:
   - `Score` — `f"{result.score:.4f}"`
   - `Note Title` — `result.title`
   - `Vault` — `result.source_vault`
   - `Heading` — `result.heading_context`
   - `Snippet` — `result.snippet[:80]`

Exit code 0 on success (including no results). Exit code 1 on settings or config error or embedder creation error.

Step 3 explanation: Typer does not expose whether the user provided `--limit` or the default was used. The recommended approach is to declare `limit` with a sentinel default (`None`) and fall back to `business.search.search_limit` when it is `None`:

```python
limit: int | None = typer.Option(None, "--limit", "-n", help="Maximum results (default: config search_limit)"),
```

Then: `effective_limit = limit if limit is not None else business.search.search_limit`.

## 10. Test specifications

### Unit tests — `tests/test_search_api.py` (new file)

All tests use `pytest.mark.unit`. No Neo4j or live embedder calls.

**Fixtures needed:**
- `make_note(title, vault, original_path, note_id)` — factory returning a `Note`.
- `make_chunk(note_id, content, heading_context, index)` — factory returning a `Chunk`.
- `mock_graph_store` — `AsyncMock(spec=GraphStore)` with `search_notes`, `get_stats` pre-configured.
- `mock_embedder` — `AsyncMock` with `embed` returning `[[0.1] * 768]`.
- `test_app` — FastAPI app fixture with `app.state.graph_store = mock_graph_store` and `app.state.embedder = mock_embedder`, router included at `/api/v1`.
- `async_client` — `httpx.AsyncClient(app=test_app, base_url="http://test")`.

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_search_returns_200` | valid `q="hello"`, `mock_graph_store.search_notes` returns 1 `ServiceSearchResult` | HTTP 200 |
| `test_search_response_schema` | 1 result returned | response JSON has keys `results`, `query`, `total` |
| `test_search_result_fields` | 1 `ServiceSearchResult` with all fields set | response `results[0]` has `note_id`, `title`, `source_vault`, `original_path`, `score`, `snippet`, `heading_context` |
| `test_search_empty_results` | `search_notes` returns `[]` | `results=[]`, `total=0`, HTTP 200 |
| `test_search_vault_filter_passed` | `GET /api/v1/search?q=hello&vault=v1` | `search_notes` called with `vault_filter="v1"` |
| `test_search_limit_passed` | `GET /api/v1/search?q=hello&limit=5` | `search_notes` called with `limit=5` |
| `test_search_query_echoed` | `q="my query"` | response `query == "my query"` |
| `test_search_total_matches_results_length` | 3 results | response `total == 3` |
| `test_search_missing_q_returns_422` | `GET /api/v1/search` (no `q`) | HTTP 422 |
| `test_search_limit_zero_returns_422` | `GET /api/v1/search?q=hello&limit=0` | HTTP 422 |
| `test_search_limit_above_max_returns_422` | `GET /api/v1/search?q=hello&limit=51` | HTTP 422 |
| `test_stats_returns_200` | `get_stats` returns valid dict | HTTP 200 |
| `test_stats_response_schema` | `get_stats` returns all required keys | response JSON has `note_count`, `chunk_count`, `similarity_edge_count`, `related_to_edge_count`, `links_to_edge_count`, `vault_names` |
| `test_stats_values_match_graph_store` | `get_stats` returns `{"note_count": 3, "chunk_count": 9, "similarity_edge_count": 15, "related_to_edge_count": 4, "links_to_edge_count": 2, "vault_names": ["v1", "v2"]}` | all response fields match exactly |
| `test_stats_empty_graph` | `get_stats` returns all zeros and empty vault_names | all response counts 0, `vault_names=[]` |

### Unit tests for `get_note_by_id` — `tests/test_neo4j_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_get_note_by_id_found` | mock session returns one Note node row | returns `Note` with `id`, `title`, `vault`, `original_path`, `content` set correctly |
| `test_get_note_by_id_not_found` | mock session `.single()` returns `None` | returns `None` |
| `test_get_note_by_id_uuid_coerced` | `note_id` passed as a `UUID` object | Cypher query receives `str(note_id)` as the `$id` parameter |

### Unit tests for `get_stats` — `tests/test_neo4j_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_get_stats_returns_all_keys` | mock sessions return numeric data | returned dict has all six keys |
| `test_get_stats_vault_names_sorted` | note query returns `vault_names=["z_vault", "a_vault"]` | `result["vault_names"] == ["a_vault", "z_vault"]` |
| `test_get_stats_empty_graph` | note query returns no record; all count queries return 0 | all int fields `== 0`, `vault_names == []` |

### Unit tests for `search_notes` — `tests/test_neo4j_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_search_notes_returns_results` | `find_similar_chunks` returns 2 chunks from different notes; `get_note_by_id` returns valid Notes | list of 2 `SearchResult` objects |
| `test_search_notes_dedup_keeps_best_score` | 3 chunks all from the same note, scores `[0.9, 0.7, 0.8]` | single `SearchResult` with `score=0.9` |
| `test_search_notes_vault_filter` | 2 results from vaults `"v1"` and `"v2"`, `vault_filter="v1"` | only the `"v1"` result returned |
| `test_search_notes_orphaned_chunk_skipped` | `get_note_by_id` returns `None` for one of 2 chunks | 1 result; no exception |
| `test_search_notes_sorted_by_score_desc` | 3 notes with scores `[0.8, 0.95, 0.72]` | returned order `[0.95, 0.80, 0.72]` |
| `test_search_notes_limit_applied` | `limit=2`, 5 unique notes available | 2 results returned |
| `test_search_notes_empty_graph` | `find_similar_chunks` returns `[]` | empty list returned |
| `test_search_notes_snippet_truncated` | chunk with `content` longer than 200 chars | `result.snippet == chunk.content[:200]` |
| `test_search_notes_overfetch_factor` | `limit=3` | `find_similar_chunks` called with `limit=15` (`limit * 5`) |

### Unit tests for config — `tests/test_config.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_search_config_default` | `BusinessConfig()` | `business.search.search_limit == 10` |
| `test_search_config_from_yaml` | YAML with `search:\n  search_limit: 25` | `business.search.search_limit == 25` |

### Unit tests for CLI — `tests/test_cli.py` (additions, class `TestSearchCommand`)

| Test | Description |
|------|-------------|
| `test_search_command_exits_zero` | Patch `_run_search` as `AsyncMock` returning 1 `ServiceSearchResult`; invoke `kg search "hello" --config <path>` → exit code 0 |
| `test_search_command_prints_table` | Same patch; stdout contains the note title and `f"{score:.4f}"` |
| `test_search_command_no_results` | Patch `_run_search` returns `[]`; stdout contains `"No results found."` |
| `test_search_command_vault_flag` | Patch `_run_search`; `kg search "hello" --vault myvault` → `_run_search` called with `vault="myvault"` |
| `test_search_command_limit_flag_overrides_config` | Patch `_run_search`; `kg search "hello" --limit 5` → `_run_search` called with `limit=5` |
| `test_search_command_config_not_found` | `_load_business_config` raises `FileNotFoundError` → exit code 1 |
| `test_search_command_settings_error` | `_load_app_settings` raises `Exception` → exit code 1 |
| `test_search_command_embedder_error` | `_make_embedder` raises `ValueError` → exit code 1 |

## 11. Edge cases

- Query that matches no chunks (threshold too high or embeddings distant): `search_notes` returns `[]`; endpoint returns HTTP 200 with empty results.
- `vault_filter` that matches no notes even though chunks are found: empty results, HTTP 200.
- All chunks returned by `find_similar_chunks` have orphaned Note references: results list is empty, no exception raised.
- `limit=1`: only the top result returned; `find_similar_chunks` called with `limit=5` (over-fetch factor applied).
- `limit=50` (maximum allowed by API): enforced by `Query(le=50)` constraint; `find_similar_chunks` called with `limit=250`.
- Multiple chunks from the same note: deduplication keeps only the highest-scoring chunk; that chunk's `content[:200]` becomes the snippet.
- Chunk with `heading_context=""` (no heading above it): `SearchResult.heading_context` is `""`.
- Empty graph (no Chunk nodes): `find_similar_chunks` returns `[]`; `search_notes` returns `[]`; stats endpoint returns all zeros.
- Note with `content` shorter than 200 chars: snippet equals `content` unchanged (no padding).

## 12. Dependencies and assumptions

- `find_similar_chunks` is implemented and tested (spec 08, confirmed in `neo4j_store.py`).
- `app.state.embedder` and `app.state.graph_store` are set during FastAPI lifespan (confirmed in `main.py`).
- `EmbeddingService.embed(texts: list[str]) -> list[list[float]]` (first element is the query vector). `EmbeddingService.close()` is an async method (confirmed in `main.py` lifespan shutdown).
- `Chunk.note_id` is a `UUID`; `Chunk.content` and `Chunk.heading_context` are non-null strings (confirmed in `models/note.py`).
- `Note.vault`, `Note.title`, `Note.original_path` are always non-null strings (enforced by `upsert_note`).
- The Neo4j HNSW vector index `chunk_embeddings` is created by `initialize()` (confirmed in `neo4j_store.py`).
- `GraphStore` ABC is in `services/graph_store.py`; Neo4j implementation in `services/neo4j_store.py`.
- Router is included at prefix `/api/v1` in `main.py`; new routes use paths `/search` and `/stats` relative to the router.
- `BusinessConfig.from_yaml` uses `cls.model_validate(data)` with Pydantic v2, so the new `search` sub-key is handled automatically without changes to `from_yaml`.
