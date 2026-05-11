# 11 — Roadmap

## Step 1: Add `content_hash` field to the Note model

Add `content_hash: str | None = None` to the `Note` Pydantic model in `models/note.py`. This field holds the SHA-256 hex digest of the raw file content at ingestion time. It is `None` for notes ingested before this spec was implemented.

**Done when:** `Note` has a `content_hash` field that is optional and defaults to `None`. Existing tests that construct `Note` objects still pass without supplying `content_hash`.

## Step 2: Add GraphStore methods for incremental sync

Add four abstract methods to `GraphStore` and implement them in `Neo4jGraphStore`:

- `get_all_note_paths(vault: str) -> list[tuple[str, str | None]]` — returns `(original_path, content_hash)` pairs for all Note nodes belonging to a vault. `content_hash` may be `None` for notes stored before this spec.
- `get_note_by_path(vault: str, path: str) -> Note | None` — returns the Note node for a given vault + original_path, or `None` if not found.
- `delete_note(note_id: UUID) -> None` — deletes a Note node, all its Chunk nodes, and all incident edges (DETACH DELETE on the Note, then delete orphaned Chunks).
- `set_note_content_hash(note_id: UUID, content_hash: str) -> None` — sets `n.content_hash` on the Note node identified by `note_id`.

Also update `upsert_note` in `Neo4jGraphStore` to persist `content_hash` when it is set on the Note being upserted.

**Done when:** All four methods pass their unit tests. `upsert_note` persists `content_hash` when present.

## Step 3: Add `link_chunks` to SemanticLinker

Add a `link_chunks` method to `SemanticLinker` (in `services/linker.py`) that accepts a list of chunk IDs and runs similarity search only for those chunks, creating SIMILAR_TO edges as `link_all` does. This is used by `SyncPipeline` to avoid re-linking the entire graph after a partial ingest.

**Done when:** `link_chunks(chunk_ids)` creates SIMILAR_TO edges for the specified chunks only, with the same same-note exclusion and threshold logic as `link_all`. Returns a `LinkResult`.

## Step 4: Define SyncPhase, SyncProgressCallback, and SyncResult

Define supporting types in `services/sync_pipeline.py`:

- `SyncPhase(StrEnum)` with values `SCANNING`, `EMBEDDING`, `DELETING`, `LINKING`.
- `SyncProgressCallback = Callable[[SyncPhase, int, int, str], None]`
- `SyncResult` dataclass with fields: `vault`, `notes_added`, `notes_updated`, `notes_deleted`, `notes_unchanged`, `chunks_added`, `chunks_deleted`, `duration_seconds`.

**Done when:** Types are importable and `SyncResult` can be constructed with all required fields.

## Step 5: Implement SyncPipeline service

Create `services/sync_pipeline.py` with the `SyncPipeline` class and its `sync()` method. The method runs the full incremental algorithm: SCANNING → DELETING → EMBEDDING → LINKING, emitting progress callbacks at each phase.

**Done when:** All unit tests in `tests/test_sync_pipeline.py` pass: new notes are added, unchanged notes are skipped, changed notes are updated, deleted notes are removed, empty vaults produce all-zero results.

## Step 6: Add `kg sync` CLI command

Add a `sync` command to `cli.py` following the same structure as `kg ingest`. It accepts a `vault_name` positional argument and a `--config` option. It resolves the vault from `BusinessConfig`, runs `SyncPipeline.sync()` with a Rich progress bar covering all four phases, and prints a result table.

**Done when:** `kg sync <vault_name> --config config.yaml` exits 0, displays progress, and prints a table with all `SyncResult` fields. Unknown vault exits 1. Config not found exits 1.

## Step 7: Add `POST /api/v1/sync` endpoint

Add a `/sync` route to `api/routes.py`. The request body contains `vault` (string). The response body maps to `SyncResponse`.

**Done when:** `POST /api/v1/sync` with a valid vault name returns HTTP 200 with a body containing all `SyncResponse` fields.
