# 08 — Roadmap

## Step 1: Add `get_all_chunks` to GraphStore

The linker needs to iterate all chunks with embeddings. Add `get_all_chunks` abstract method + Neo4j implementation.

**Done when:** `get_all_chunks()` returns all Chunk nodes that have non-null embeddings.

## Step 2: Implement SemanticLinker service

Create `services/linker.py` with `SemanticLinker` class. Two main methods:
- `link_all()` — iterate chunks, find similar neighbors, create SIMILAR_TO edges
- `derive_note_relationships()` — aggregate SIMILAR_TO into RELATED_TO between Notes

**Done when:** Linker creates SIMILAR_TO and RELATED_TO edges correctly, with same-note exclusion and idempotency.

## Step 3: Add `kg link` CLI command

Wire the linker into the CLI with Rich progress bars for both the SIMILAR_TO and RELATED_TO phases.

**Done when:** `kg link` runs the linker end-to-end with progress display.

## Step 4: Add `POST /api/v1/link` API endpoint

Expose linking via the FastAPI server.

**Done when:** `/api/v1/link` triggers the linker and returns stats.
