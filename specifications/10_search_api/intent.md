# 10 — Search API

Amends: 04_ingestion_api (adds search and stats endpoints), 03_cli (adds search command)

## Problem

The Knowledge Garden graph contains Notes, Chunks with embeddings, LINKS_TO edges, and RELATED_TO edges. All of this structure is queryable only by writing Cypher directly against Neo4j. There is no way for a user or external tool to ask a plain-text question and receive a ranked list of relevant notes, nor to get a snapshot of what the graph contains.

Two gaps remain before Phase 6 of the roadmap is complete:

1. No semantic search endpoint. A user cannot type a question and get relevant notes back. The vector index and embedding service exist but are not exposed over HTTP or the CLI.
2. No stats endpoint. There is no way to verify what has been ingested, how many edges were created, or which vaults are present without querying Neo4j directly.

## Desired behavior

### Search

Running `kg search "query text"` (or `GET /api/v1/search?q=...`) embeds the query, runs a KNN vector search over Chunk nodes, groups the best matching chunk per parent Note, and returns results sorted by similarity score descending. An optional `--vault` flag (or `vault` query parameter) restricts results to a single source vault. The `limit` parameter controls the maximum number of notes returned. Each result includes a `snippet`: the matching chunk's text truncated to 200 characters.

### Stats

`GET /api/v1/stats` returns a single JSON object with counts of Note nodes, Chunk nodes, SIMILAR_TO edges, RELATED_TO edges, and LINKS_TO edges, as well as the list of distinct vault names present in the graph. This allows quick verification that ingestion, linking, and deduplication ran correctly.

## Non-goals

- Full-text (BM25/keyword) search. This spec covers vector search only.
- Re-ranking with an LLM. Raw embedding similarity is the only ranking signal.
- Returning chunk-level results. The unit of a search result is a note, not an individual chunk.
- Modifying or updating notes via the search endpoint.

## Open questions

None. All design decisions are encoded in this spec.
