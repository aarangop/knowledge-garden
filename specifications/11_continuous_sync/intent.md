# 11 — Continuous Sync

Amends: 05_ingestion_pipeline (adds incremental variant), 03_cli (adds sync command), 04_ingestion_api (adds sync endpoint)

## Problem

The current `kg ingest` command performs a full vault scan every time: every note is parsed, chunked, embedded, and upserted. Embedding API calls dominate the cost. For a vault of thousands of notes, re-running ingest after editing five files is wasteful — the user pays for 995 unnecessary embed calls to process 5 changed files.

There is also no deletion detection. If a user deletes or renames a note file, the stale Note node and its Chunk nodes remain in Neo4j indefinitely.

## Desired behavior

Running `kg sync <vault_name>` (or `POST /api/v1/sync`) performs an incremental synchronization:

1. Scans all `.md` files in the vault on disk, parses them, and computes a SHA-256 hash of each note's parsed content (the post-frontmatter markdown body that is also stored on the Note node). Frontmatter-only edits do not count as a change because they do not affect chunks or embeddings.
2. Compares each note's hash against the `content_hash` stored on its corresponding Note node in Neo4j.
3. Notes whose hash matches are skipped entirely — no embed calls, no upserts.
4. Notes whose hash differs (or whose path does not exist in Neo4j yet) are re-chunked, re-embedded, and re-upserted. Changed notes have their old Chunk nodes deleted before new ones are written.
5. Notes that exist in Neo4j but are no longer on disk are deleted from the graph (Note node, Chunk nodes, and all incident edges).
6. After processing, semantic similarity edges are recomputed for the newly created chunks (`SIMILAR_TO`), and `RELATED_TO` Note edges are re-derived from the resulting `SIMILAR_TO` graph so that note-level relationships stay consistent with the new content.
7. A `SyncResult` is returned with counts of added, updated, deleted, and unchanged notes plus chunk statistics and elapsed time.

The sync is safe to run repeatedly. Running it on an unchanged vault costs only the Neo4j read to compare hashes — no embed calls are made and no relationships are recomputed.

## Open questions

None. All design decisions are encoded in this spec.
