# Intent: Vault Ingestion

## What

Phase 02 adds the ability to ingest an Obsidian vault into the Knowledge Garden. A single API call triggers the full pipeline: read all markdown files from a configured vault directory, split them into chunks, embed those chunks, and store everything in Neo4j. A second endpoint lets callers inspect what notes are already in the graph.

## Why

The foundation phase (01) established data models, storage abstractions, and the embedding client — but nothing actually moves data into the graph. This phase closes that gap. After this phase, a user can point the app at a vault, call `POST /api/v1/ingest`, and have all their notes parsed, chunked, embedded, and stored, ready for future semantic search and linking.

## User-visible behavior

- A user POSTs `{"vault_name": "my_vault"}` to `/api/v1/ingest` and receives a summary: how many notes were parsed, how many chunks were created, how long it took.
- If the vault name does not match any entry in `config.yaml`, the API returns a 404 with a clear message.
- A user GETs `/api/v1/notes` to see all notes currently in the graph with their titles, vault names, paths, and wikilink targets.
- Re-running ingest on the same vault is safe: all writes use upsert semantics (idempotent).

## Scope of this phase

This phase covers five discrete units of work:

1. **Parser service** — walks a vault directory and produces `Note` objects with wikilinks and attachment references extracted.
2. **Chunker service** — splits a `Note` into `Chunk` objects by heading structure (all heading levels) and size limits.
3. **HuggingFace embedder** — adds HuggingFace Inference API as an alternative embedding provider, selectable via `config.embedding.provider`; the lifespan now dispatches to either `TogetherAIEmbedder` or `HuggingFaceEmbedder` based on that value.
4. **Ingest endpoint** — orchestrates parser, chunker, embedder, and graph store into the full pipeline.
5. **Notes listing endpoint** — reads all notes from the graph store and returns them.

This phase also amends the `Note` model from spec 01 by adding an `attachment_refs` field to store references to non-note attachments (images, PDFs, etc.) found in wikilinks.

## Out of scope

- Semantic link discovery (similarity-based `RELATED_TO` edges) — future phase.
- Wikilink resolution (mapping `outgoing_links` strings to actual `Note` IDs) — future phase.
- Pagination on the notes listing endpoint.
- Incremental ingestion (detecting changed files) — future phase.
- Rewriting inline note transclusion references (`![[note name]]`) to use output vault filenames — future exporter phase. The parser captures these in `outgoing_links`; the exporter must preserve the `![[...]]` embed syntax when rewriting paths.

## Open questions

- None. All behavior is fully specified.
