# 08 — Semantic Linking

Amends: 03_cli (adding link command), 02_ingestion (linking is the post-ingestion step)

## Problem

After ingestion, the graph contains Note nodes with LINKS_TO edges (explicit wikilinks) and Chunk nodes with embeddings. But the key value of Knowledge Garden — discovering implicit cross-vault relationships — is missing. There are no SIMILAR_TO edges between chunks and no RELATED_TO edges between notes from different vaults.

Deduplication was handled during ingestion (spec 07). This spec focuses purely on discovering and persisting semantic relationships.

## Desired behavior

- Run a `kg link` command that iterates all embedded chunks, finds semantically similar neighbors, and creates SIMILAR_TO edges between them (excluding same-note pairs).
- After SIMILAR_TO edges are created, derive RELATED_TO edges between parent Notes by aggregating chunk similarities.
- The process is idempotent (MERGE for edges) and can be re-run safely.
- Progress is reported via the CLI with Rich progress bars.
- Linking threshold and max_neighbors are configurable via `config.yaml` (using existing `LinkingConfig`).

## Outcome

After running `kg link`, the graph contains both explicit (LINKS_TO) and discovered (RELATED_TO) relationships. Cross-vault knowledge connections are surfaced and queryable.
