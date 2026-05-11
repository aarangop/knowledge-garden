# 11 — Contract

## 1. Note model change

File: `models/note.py`

Add one optional field to the existing `Note` Pydantic model:

```python
content_hash: str | None = None
# SHA-256 hex digest of the raw file content at parse time.
# None for notes ingested before spec 11 was implemented.
```

No other fields on `Note` change. All existing code that constructs `Note` without `content_hash` continues to work.

## 2. GraphStore additions

File: `services/graph_store.py`

Four new abstract methods added to `GraphStore`:

### `get_all_note_paths`

```python
@abstractmethod
async def get_all_note_paths(self, vault: str) -> dict[str, str | None]:
    """Return a mapping of original_path → content_hash for all Notes in a vault.

    content_hash is None for notes stored before spec 11 (no hash persisted yet).
    Returns an empty dict if the vault has no notes in the graph.

    Args:
        vault: The vault name string (matches Note.vault).

    Returns:
        dict[str, str | None] keyed by original_path. Order is not guaranteed.
        original_path values are unique within a single vault (enforced by the
        ingest/sync writes — a vault never holds two notes at the same path).
    """
    ...
```

Neo4j implementation:

```cypher
MATCH (n:Note {vault: $vault})
RETURN n.original_path AS path, n.content_hash AS hash
```

Returns `{record["path"]: record["hash"] for record in records}`.

### `get_note_by_path`

```python
@abstractmethod
async def get_note_by_path(self, vault: str, path: str) -> Note | None:
    """Return the Note node for a given vault + original_path, or None.

    Args:
        vault: The vault name string.
        path: The original_path string (relative path within the vault).

    Returns:
        A fully populated Note object, or None if not found.
    """
    ...
```

Neo4j implementation:

```cypher
MATCH (n:Note {vault: $vault, original_path: $path})
RETURN n
```

Constructs a `Note` from the node properties. Returns `None` if no record is returned. The `content_hash` field is populated from `n.content_hash` (which may be `None`).

### `delete_note`

```python
@abstractmethod
async def delete_note(self, note_id: UUID) -> None:
    """Delete a Note node, all its Chunk nodes, and all incident edges.

    Uses DETACH DELETE on the Note to remove all edges to/from it.
    Then deletes Chunk nodes that were connected via HAS_CHUNK
    (they become orphaned after the Note is deleted, so we clean them up
    in a separate query using the pre-collected chunk IDs).

    Args:
        note_id: UUID of the Note to delete.
    """
    ...
```

Neo4j implementation — two queries in sequence:

```cypher
-- Query 1: collect chunk IDs before deleting the note
MATCH (n:Note {id: $id})-[:HAS_CHUNK]->(c:Chunk)
RETURN c.id AS chunk_id

-- Query 2: detach-delete the Note (removes all incident edges)
MATCH (n:Note {id: $id})
DETACH DELETE n

-- Query 3: delete the now-orphaned Chunk nodes
UNWIND $chunk_ids AS cid
MATCH (c:Chunk {id: cid})
DETACH DELETE c
```

Implementation note: run query 1 first to collect `chunk_ids`, then query 2, then query 3. If query 1 returns no chunks, skip query 3. All three queries run in the same logical operation but separate sessions (async driver pattern used throughout).

### `set_note_content_hash`

```python
@abstractmethod
async def set_note_content_hash(self, note_id: UUID, content_hash: str) -> None:
    """Persist the content_hash on a Note node.

    Args:
        note_id: UUID of the Note.
        content_hash: SHA-256 hex digest string (64 hex characters).
    """
    ...
```

Neo4j implementation:

```cypher
MATCH (n:Note {id: $id})
SET n.content_hash = $content_hash
```

### `upsert_note` update

The existing `upsert_note` in `Neo4jGraphStore` must be updated to also persist `content_hash` when it is set on the Note. Add `n.content_hash = $content_hash` to the `SET` clause:

```cypher
MERGE (n:Note {id: $id})
SET n.title = $title, n.content = $content,
    n.vault = $vault, n.original_path = $original_path,
    n.content_hash = $content_hash
```

Pass `content_hash=note.content_hash` as a parameter (value may be `None`; Neo4j stores `null`).

## 3. SemanticLinker addition: `link_chunks`

File: `services/linker.py`

New method on `SemanticLinker`:

```python
async def link_chunks(
    self,
    chunk_ids: list[UUID],
    progress_callback: ProgressCallback | None = None,
) -> LinkResult:
    """Run similarity search for a specific set of chunks and create SIMILAR_TO edges.

    Only the chunks identified by chunk_ids are used as query vectors.
    Their similar neighbors (from the entire graph) are found via vector search.
    Same-note exclusion applies: matches with the same note_id as the query chunk
    are not linked.

    This is used by SyncPipeline to link only newly ingested chunks, avoiding
    a full re-link of the entire graph.

    Args:
        chunk_ids: UUIDs of the chunks to link. Chunks not found in the graph
                   (e.g., deleted between scheduling and execution) are silently
                   skipped.
        progress_callback: Optional callback with signature
                           (LinkPhase, current, total, detail_str).

    Returns:
        LinkResult with chunks_processed (= len(chunk_ids) minus skipped),
        similarity_edges_created, note_relationships_derived=0
        (derive_related_to is NOT called by this method; the caller decides
        whether to run it), and duration_seconds.
    """
```

Algorithm:

1. For each `chunk_id` in `chunk_ids`, fetch the chunk individually via `graph_store.get_chunk_by_id(chunk_id)` (see section 4 below). The bulk helper `get_chunks_for_note` is intentionally not used here because the input set is a flat list of chunk IDs that may span many notes.
2. If `get_chunk_by_id` returns `None`, or the returned chunk has `embedding is None`, skip it (cannot run vector search without an embedding) and log a warning.
3. For each remaining chunk: call `graph_store.find_similar_chunks(embedding=chunk.embedding, limit=max_neighbors, threshold=threshold)`.
4. Filter out matches where `match.note_id == chunk.note_id` (same-note exclusion).
5. For each surviving match, call `graph_store.create_similarity(chunk.id, match.id, score)`.
6. Emit progress callback `(LinkPhase.SIMILAR, current, total, f"{edges} edges")` after each chunk.
7. Return `LinkResult(chunks_processed=processed, similarity_edges_created=edges, note_relationships_derived=0, duration_seconds=elapsed)`.

`note_relationships_derived` is left at 0 here because RELATED_TO derivation is graph-wide and is run once by the caller (`SyncPipeline`) after all `link_chunks` work completes. See §6 step 4.

## 4. GraphStore addition: `get_chunk_by_id`

File: `services/graph_store.py`

```python
@abstractmethod
async def get_chunk_by_id(self, chunk_id: UUID) -> Chunk | None:
    """Return a single Chunk by its UUID, or None if not found.

    Args:
        chunk_id: UUID of the Chunk node.

    Returns:
        Chunk with embedding populated, or None.
    """
    ...
```

Neo4j implementation:

```cypher
MATCH (c:Chunk {id: $id})
RETURN c
```

Construct a `Chunk` from the node properties. Return `None` if no record. The `embedding` field is populated from `c.embedding` (may be `None` for un-embedded chunks).

## 5. SyncPhase, SyncProgressCallback, SyncResult

File: `services/sync_pipeline.py`

```python
from enum import StrEnum
from dataclasses import dataclass
from collections.abc import Callable

class SyncPhase(StrEnum):
    SCANNING  = "scanning"
    DELETING  = "deleting"
    EMBEDDING = "embedding"
    LINKING   = "linking"

SyncProgressCallback = Callable[[SyncPhase, int, int, str], None]

@dataclass
class SyncResult:
    vault: str
    notes_added: int
    notes_updated: int
    notes_deleted: int
    notes_unchanged: int
    chunks_added: int
    chunks_deleted: int
    similarity_edges_created: int       # SIMILAR_TO edges from link_chunks over new chunks
    note_relationships_derived: int     # RELATED_TO edges produced by derive_related_to
    duration_seconds: float
```

`chunks_deleted` counts every Chunk removed during this sync run — both chunks attached to notes that were deleted from disk (DELETED set) and chunks attached to notes whose content changed (CHANGED set, deleted via `delete_note` before re-upserting). Chunks that are upserted as part of new/changed notes count toward `chunks_added` (not `chunks_deleted`).

## 6. SyncPipeline service

File: `services/sync_pipeline.py`

```python
class SyncPipeline:
    def __init__(
        self,
        parser: MarkdownParser,
        chunker: NoteChunker,
        embedder: EmbeddingService,
        graph_store: GraphStore,
        linker: SemanticLinker,
        embed_batch_size: int = 32,
        dedup_threshold: float = 0.95,
    ) -> None:
        """
        Args:
            parser: MarkdownParser instance (spec 02).
            chunker: NoteChunker instance (spec 02).
            embedder: EmbeddingService instance.
            graph_store: GraphStore backend (spec 01).
            linker: SemanticLinker instance (spec 08).
            embed_batch_size: Number of chunks per embedding API call.
            dedup_threshold: Cosine similarity threshold above which a new
                             chunk is considered a duplicate and skipped.
        """

    async def sync(
        self,
        vault_config: VaultConfig,
        progress_callback: SyncProgressCallback | None = None,
    ) -> SyncResult:
        """Incrementally synchronise a vault on disk with Neo4j.

        Algorithm:
        1. SCANNING phase:
           a. Call parser.parse_vault(vault_config) → list[Note] (disk_notes).
              The parser strips frontmatter; note.content is the post-frontmatter
              markdown body.
           b. For each disk note, compute SHA-256 of its parsed content:
                  hashlib.sha256(note.content.encode("utf-8")).hexdigest()
              Store this in note.content_hash. This hash matches what is (or will
              be) persisted on the Note node, so frontmatter-only edits do not
              register as a change.
           c. Call graph_store.get_all_note_paths(vault_config.name)
              → dict[str, str | None] (path → stored_hash).
           d. Classify each disk note:
              - NEW: path not in stored_hash map.
              - CHANGED: path in stored_hash map but hashes differ
                         (or stored hash is None — treat None as "must re-embed").
              - UNCHANGED: hashes match exactly.
           e. DELETED: paths in stored_hash map that are not on disk.
           f. Emit progress callback once per disk note scanned:
              (SyncPhase.SCANNING, current, total, note.original_path).

        2. DELETING phase:
           For each deleted path AND for each CHANGED note (pre-delete):
           a. Call graph_store.get_note_by_path(vault, path) to get the note_id.
              If None (race), log a warning and skip that path.
           b. Get chunk count via graph_store.get_chunks_for_note(note_id) and
              add it to chunks_deleted.
           c. Call graph_store.delete_note(note_id) (DETACH DELETE removes the
              Note, all its Chunks, and all incident edges including LINKS_TO,
              RELATED_TO, SIMILAR_TO from this note's chunks).
           d. For DELETED notes, increment notes_deleted.
              For CHANGED notes, do not increment notes_deleted; the matching
              upsert in step 3 will count toward notes_updated instead.
           e. Emit progress callback:
              (SyncPhase.DELETING, current, total_to_delete, path).

        3. EMBEDDING phase:
           a. Collect all NEW + CHANGED notes.
           b. CHANGED notes already had their old Note + Chunk nodes removed in
              step 2. Both NEW and CHANGED notes therefore need a fresh upsert_note
              before any chunk is written, so the HAS_CHUNK MERGE has a parent
              to attach to. (upsert_note also persists note.content_hash via the
              updated Cypher in §2.)
           c. Chunk and embed all NEW + CHANGED notes in batches of embed_batch_size,
              using the same dedup logic as IngestPipeline.
           d. Track new_chunk_ids: list[UUID] of every Chunk successfully upserted
              (i.e., not skipped as a duplicate). chunks_added is len(new_chunk_ids).
           e. After upserting, call graph_store.set_note_content_hash(note_id, hash)
              for each processed note (belt-and-braces: upsert_note already wrote
              the hash, but this re-asserts it after all chunks are persisted so
              that a partial failure mid-batch leaves the hash unset for the
              still-stale rows).
           f. Increment notes_added (for NEW) or notes_updated (for CHANGED) per note.
           g. Emit progress callback:
              (SyncPhase.EMBEDDING, current, total_chunks, f"batch {b}/{total_batches}").

        4. LINKING phase:
           a. If new_chunk_ids is empty, set similarity_edges_created=0,
              note_relationships_derived=0, and skip to step 5 (do not call
              link_chunks or derive_related_to).
           b. Otherwise, call linker.link_chunks(new_chunk_ids,
              progress_callback=linking_cb) where linking_cb translates LinkPhase
              callbacks to SyncPhase.LINKING callbacks.
              Capture link_result.similarity_edges_created.
           c. Call graph_store.derive_related_to(threshold=linker._threshold)
              and capture the returned int into note_relationships_derived.
              This step rebuilds RELATED_TO across the entire graph using the
              current SIMILAR_TO edges; it is required because the new/changed
              chunks may have created or altered the SIMILAR_TO graph in ways
              that affect note-level relationships.
           d. Emit final progress callback:
              (SyncPhase.LINKING, total_new_chunks, total_new_chunks, detail).

        5. Return SyncResult including similarity_edges_created and
           note_relationships_derived.

        Args:
            vault_config: VaultConfig with .name and .path.
            progress_callback: Optional callable invoked at each phase step.

        Returns:
            SyncResult with per-category counts and duration.
        """
```

### SHA-256 helper

Internal function (module-level, not part of the public interface):

```python
def _compute_hash(content: str) -> str:
    """Return the SHA-256 hex digest of content encoded as UTF-8."""
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()
```

## 7. CLI: `kg sync` command

File: `cli.py`

Internal coroutine:

```python
async def _run_sync(
    vault_config: VaultConfig,
    embedder: EmbeddingService,
    graph_store: GraphStore,
    business: BusinessConfig,
) -> SyncResult:
    from knowledge_garden.services.chunker import NoteChunker
    from knowledge_garden.services.linker import SemanticLinker
    from knowledge_garden.services.parser import MarkdownParser
    from knowledge_garden.services.sync_pipeline import SyncPhase, SyncPipeline

    await graph_store.initialize()
    try:
        linker = SemanticLinker(
            graph_store,
            threshold=business.linking.threshold,
            max_neighbors=business.linking.max_neighbors,
        )
        pipeline = SyncPipeline(
            parser=MarkdownParser(),
            chunker=NoteChunker(business.chunking),
            embedder=embedder,
            graph_store=graph_store,
            linker=linker,
            embed_batch_size=business.embedding.batch_size,
            dedup_threshold=business.dedup.threshold,
        )
        # Rich progress bar covers all four SyncPhase values.
        # Each phase is shown as a separate task, made visible when active.
        with Progress(...) as progress:
            ...
            return await pipeline.sync(vault_config, progress_callback=progress_callback)
    finally:
        await graph_store.close()
```

The `sync` command:

```python
@app.command()
def sync(
    vault_name: str,
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
```

Behavior:
1. Load `AppSettings` — on error, echo message and `raise typer.Exit(1)`.
2. Load `BusinessConfig` from `config_path` — on `FileNotFoundError`, echo message and `raise typer.Exit(1)`.
3. Resolve vault: `next((v for v in business.vaults if v.name == vault_name), None)` — if `None`, echo `"Vault '{vault_name}' not found in configuration"` and `raise typer.Exit(1)`.
4. Create embedder via `_make_embedder` and graph_store via `_make_graph_store`.
5. Run `asyncio.run(_run_sync(vault_config, embedder, graph_store, business))`.
6. Print a Rich `Table` with rows:
   - `"Notes added"` / `result.notes_added`
   - `"Notes updated"` / `result.notes_updated`
   - `"Notes deleted"` / `result.notes_deleted`
   - `"Notes unchanged"` / `result.notes_unchanged`
   - `"Chunks added"` / `result.chunks_added`
   - `"Chunks deleted"` / `result.chunks_deleted`
   - `"Similarity edges"` / `result.similarity_edges_created`
   - `"Note relationships"` / `result.note_relationships_derived`
   - `"Duration"` / `f"{result.duration_seconds:.2f}s"`

## 8. API: `POST /api/v1/sync`

File: `api/routes.py`

The sync endpoint accepts the vault to sync directly in the request body — both its `name` (used for `Note.vault` and `get_all_note_paths`) and its filesystem `path` (used by the parser). This avoids loading `BusinessConfig` into the FastAPI server, which spec 04 (config split) explicitly forbids: the FastAPI process reads only environment variables via `AppSettings`. All business-config-driven knobs (chunking, embedding batch size, dedup/linking thresholds) fall back to their `BusinessConfig` defaults — i.e., the same defaults the YAML would produce when fields are omitted.

### Request schema

```python
class SyncRequest(BaseModel):
    vault: str         # vault name (matches Note.vault)
    path: str          # filesystem path to the vault root, used by parser
```

### Response schema

```python
class SyncResponse(BaseModel):
    vault: str
    notes_added: int
    notes_updated: int
    notes_deleted: int
    notes_unchanged: int
    chunks_added: int
    chunks_deleted: int
    similarity_edges_created: int
    note_relationships_derived: int
    duration_seconds: float
```

### Handler

```python
@router.post("/sync")
async def sync_vault(body: SyncRequest, request: Request) -> SyncResponse:
    from knowledge_garden.config import (
        ChunkingConfig, DedupConfig, EmbeddingConfig, LinkingConfig, VaultConfig,
    )
    from knowledge_garden.services.chunker import NoteChunker
    from knowledge_garden.services.linker import SemanticLinker
    from knowledge_garden.services.parser import MarkdownParser
    from knowledge_garden.services.sync_pipeline import SyncPipeline

    graph_store = request.app.state.graph_store
    embedder = request.app.state.embedder

    # Use library defaults; the API does not load BusinessConfig.
    chunking = ChunkingConfig()
    embedding = EmbeddingConfig()
    dedup = DedupConfig()
    linking = LinkingConfig()

    linker = SemanticLinker(
        graph_store,
        threshold=linking.threshold,
        max_neighbors=linking.max_neighbors,
    )
    pipeline = SyncPipeline(
        parser=MarkdownParser(),
        chunker=NoteChunker(chunking),
        embedder=embedder,
        graph_store=graph_store,
        linker=linker,
        embed_batch_size=embedding.batch_size,
        dedup_threshold=dedup.threshold,
    )
    vault_config = VaultConfig(name=body.vault, path=body.path)
    result = await pipeline.sync(vault_config)
    return SyncResponse(
        vault=result.vault,
        notes_added=result.notes_added,
        notes_updated=result.notes_updated,
        notes_deleted=result.notes_deleted,
        notes_unchanged=result.notes_unchanged,
        chunks_added=result.chunks_added,
        chunks_deleted=result.chunks_deleted,
        similarity_edges_created=result.similarity_edges_created,
        note_relationships_derived=result.note_relationships_derived,
        duration_seconds=result.duration_seconds,
    )
```

Error cases:
- `parser.parse_vault` raises (e.g., path does not exist, not a directory): the exception propagates and FastAPI returns HTTP 500. The CLI provides cleaner error messages; the API surface is intentionally minimal.
- `graph_store` unavailable: HTTP 503 (pre-existing lifespan error, same as other endpoints).

Lifespan note: `app.state.embedder` is already set by the existing lifespan (`main.py`). The sync endpoint does **not** require `app.state.business_config`. No changes to `main.py` are required.

## 9. Configuration

No new configuration fields are required. `SyncPipeline` inherits its parameters from the existing `BusinessConfig`:

- `business.embedding.batch_size` → `embed_batch_size`
- `business.dedup.threshold` → `dedup_threshold`
- `business.linking.threshold` and `business.linking.max_neighbors` → passed to `SemanticLinker`

## 10. Test specifications

### Unit tests — `tests/test_sync_pipeline.py`

All tests use `pytest.mark.unit`. All dependencies (parser, chunker, embedder, graph_store, linker) are mocked.

**Fixtures needed:**

- `make_note(title, vault, content, path, content_hash=None)` — factory returning a `Note`.
- `mock_graph_store` — `AsyncMock(spec=GraphStore)` with all relevant methods pre-wired.
- `mock_embedder` — `AsyncMock(spec=EmbeddingService)` returning fixed vectors.
- `mock_linker` — `AsyncMock(spec=SemanticLinker)` whose `link_chunks` returns a stub `LinkResult`.
- `make_pipeline(graph_store, embedder, linker)` — constructs a `SyncPipeline` with real parser/chunker mocked out.

| Test | Setup | Expected outcome |
|------|-------|-----------------|
| `test_sync_adds_new_notes` | disk has 1 note; `get_all_note_paths` returns `[]` | `notes_added=1`, `notes_unchanged=0`, `embedder.embed` called once |
| `test_sync_skips_unchanged_notes` | disk has 1 note; `get_all_note_paths` returns `[(path, matching_hash)]` | `notes_unchanged=1`, `notes_added=0`, `embedder.embed` NOT called |
| `test_sync_updates_changed_notes` | disk has 1 note; `get_all_note_paths` returns `[(path, different_hash)]` | `notes_updated=1`, `embedder.embed` called, `delete_note` called once (for CHANGED pre-delete) |
| `test_sync_deletes_removed_notes` | disk empty; `get_all_note_paths` returns `[(old_path, hash)]`; `get_note_by_path` returns a Note | `notes_deleted=1`, `delete_note` called once |
| `test_sync_result_shape` | disk has 1 new note | returned object is `SyncResult` with all eight fields present |
| `test_sync_progress_callback_scanning` | disk has 2 notes, both unchanged | progress_callback called at least twice with `SyncPhase.SCANNING` |
| `test_sync_progress_callback_embedding` | disk has 1 new note | progress_callback called at least once with `SyncPhase.EMBEDDING` |
| `test_sync_empty_vault` | disk empty; `get_all_note_paths` returns `[]` | all counts zero, `embedder.embed` not called, `delete_note` not called |
| `test_sync_all_unchanged` | disk has 3 notes, all hashes match | `notes_unchanged=3`, `embedder.embed` not called, `delete_note` not called |
| `test_sync_mixed` | disk has 1 new, 1 changed, 1 unchanged, 1 deleted | `notes_added=1, notes_updated=1, notes_unchanged=1, notes_deleted=1` |
| `test_sync_content_hash_stored` | disk has 1 new note | `set_note_content_hash` called with the correct SHA-256 of the note content |
| `test_sync_changed_note_old_chunks_deleted` | disk has 1 changed note | `delete_note` called before chunks are upserted |
| `test_sync_linking_phase_called_for_new_chunks` | disk has 1 new note resulting in 1 chunk | `linker.link_chunks` called with that chunk's ID |
| `test_sync_linking_skipped_when_no_new_chunks` | all notes unchanged | `linker.link_chunks` NOT called and `graph_store.derive_related_to` NOT called |
| `test_sync_derives_related_to_after_linking` | disk has 1 new note resulting in 1 chunk; `link_chunks` returns 2 SIMILAR_TO edges; `derive_related_to` returns 1 | `derive_related_to` called once after `link_chunks`; `SyncResult.similarity_edges_created == 2`; `SyncResult.note_relationships_derived == 1` |
| `test_sync_changed_note_chunks_counted_in_chunks_deleted` | disk has 1 changed note with 3 stored chunks | `chunks_deleted >= 3` (the pre-deleted chunks of the CHANGED note) |

### Unit tests for GraphStore additions — `tests/test_graph_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_get_all_note_paths_returns_dict` | mock session returns two rows `[(path1, hash1), (path2, None)]` | result is `{path1: hash1, path2: None}` |
| `test_get_all_note_paths_empty_vault` | mock session returns no rows | empty dict `{}` |
| `test_get_note_by_path_found` | mock session returns one Note node | `Note` object with all fields, including `content_hash` |
| `test_get_note_by_path_not_found` | mock session returns no rows | `None` |
| `test_delete_note_calls_detach_delete` | mock session | session `run` called with a query containing `DETACH DELETE` |
| `test_delete_note_deletes_chunks` | mock session returns chunk IDs in query 1 | third session `run` called with chunk IDs |
| `test_set_note_content_hash_runs_set` | mock session | session `run` called with a query containing `SET n.content_hash` |
| `test_get_chunk_by_id_found` | mock session returns one Chunk node | `Chunk` object with all fields |
| `test_get_chunk_by_id_not_found` | mock session returns no rows | `None` |
| `test_upsert_note_persists_content_hash` | Note with `content_hash="abc123"` | session `run` called with `content_hash="abc123"` parameter |
| `test_upsert_note_persists_null_content_hash` | Note with `content_hash=None` | session `run` called with `content_hash=None` parameter |

### Unit tests for SemanticLinker addition — `tests/test_linker.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_link_chunks_creates_similarity_edges` | two chunk IDs from different notes, `find_similar_chunks` returns a match | `create_similarity` called, `LinkResult.similarity_edges_created == 1` |
| `test_link_chunks_excludes_same_note` | chunk ID; `find_similar_chunks` returns match from same note | `create_similarity` NOT called |
| `test_link_chunks_skips_missing_chunk` | chunk ID not found by `get_chunk_by_id` | chunk skipped silently, no error |
| `test_link_chunks_skips_chunk_without_embedding` | `get_chunk_by_id` returns Chunk with `embedding=None` | chunk skipped, `find_similar_chunks` NOT called for it |
| `test_link_chunks_empty_list` | empty `chunk_ids` | returns `LinkResult(chunks_processed=0, similarity_edges_created=0, note_relationships_derived=0, ...)` |
| `test_link_chunks_does_not_call_derive_related_to` | any input | `derive_related_to` NOT called |
| `test_link_chunks_progress_callback` | one chunk ID | callback called with `LinkPhase.SIMILAR` |

### Unit tests for CLI — `tests/test_cli.py` (additions, class `TestSyncCommand`)

| Test | Description |
|------|-------------|
| `test_sync_command_exits_zero` | Patch `_run_sync` as `AsyncMock` returning a valid `SyncResult`; invoke `kg sync vault1 --config <path>` → exit code 0 |
| `test_sync_command_prints_summary` | Same patch; output contains `"Notes added"` and the count |
| `test_sync_command_unknown_vault_exits_nonzero` | Vault name not in `business.vaults`; invoke `kg sync unknown --config <path>` → exit code 1 |
| `test_sync_command_config_not_found` | Patch `_load_business_config` to raise `FileNotFoundError` → exit code 1 |
| `test_sync_command_settings_error` | Patch `_load_app_settings` to raise `Exception` → exit code 1 |

### Unit tests for API — `tests/test_notes_api.py` (additions, class `TestSyncEndpoint`)

| Test | Description |
|------|-------------|
| `test_sync_endpoint_returns_200` | Mock `SyncPipeline.sync` to return a `SyncResult`; `POST /api/v1/sync` with `{"vault": "v1", "path": "/some/path"}` → HTTP 200 |
| `test_sync_endpoint_response_schema` | Response JSON contains keys `vault`, `notes_added`, `notes_updated`, `notes_deleted`, `notes_unchanged`, `chunks_added`, `chunks_deleted`, `similarity_edges_created`, `note_relationships_derived`, `duration_seconds` |
| `test_sync_endpoint_missing_path_returns_422` | `POST /api/v1/sync` with `{"vault": "v1"}` (no `path`) → HTTP 422 (Pydantic validation error) |

## 11. Edge cases

- **Stored hash is `None`** (note ingested before spec 11): treat as CHANGED — re-embed and update.
- **Frontmatter-only edit on disk**: the parser strips frontmatter before producing `note.content`, so the SHA-256 over `note.content` is unchanged → note is classified UNCHANGED. This is intentional: chunks and embeddings derive from the body, not the frontmatter, so re-embedding would be wasted work.
- **Vault directory does not exist**: `parser.parse_vault` raises an error; let it propagate to the caller uncaught. The CLI will surface it.
- **All files deleted**: `delete_note` is called for every path in Neo4j; `notes_deleted` equals the previous vault size.
- **Zero notes on disk and zero notes in graph**: return all-zero `SyncResult`.
- **Chunk with no embedding** (embed call failed): dedup check is skipped (same fail-open logic as `IngestPipeline`).
- **`get_note_by_path` returns `None` for a path that was listed by `get_all_note_paths`**: skip deletion for that path and log a warning. This is a race condition that is extremely unlikely but must be handled gracefully.
- **`link_chunks` called with chunk IDs where some have no embedding**: `get_chunk_by_id` returns a Chunk with `embedding=None`; skip those chunks (cannot run vector search without an embedding). Log a warning.
- **Two notes from different vaults with the same `original_path`**: `get_all_note_paths(vault)` filters by vault, so they are treated as separate entries. No collision.

## 12. Dependencies and assumptions

- `GraphStore` ABC is in `services/graph_store.py` (confirmed by reading the file).
- `Neo4jGraphStore` is in `services/neo4j_store.py` (confirmed).
- `MarkdownParser`, `NoteChunker` are from spec 02, unchanged.
- `IngestPipeline` embedding + dedup logic (spec 05/07) is re-used inside `SyncPipeline`; `SyncPipeline` does not inherit from `IngestPipeline` — it reimplements the embed loop for the subset of changed notes.
- `SemanticLinker` from spec 08 is imported and extended (not replaced).
- `LinkResult` and `LinkPhase` from spec 08 are reused by `link_chunks`.
- `VaultConfig` and `BusinessConfig` from `config.py` are unchanged.
- `EmbeddingService` abstract interface (spec 05) is unchanged.
- `find_similar_chunks` raises on vector index failure; the try/except fail-open pattern from `IngestPipeline` applies in `SyncPipeline` as well.
