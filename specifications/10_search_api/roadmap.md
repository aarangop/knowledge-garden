# 10 — Roadmap

## Step 1: Add `SearchResult` domain model and `search_notes` to GraphStore

Define a `SearchResult` dataclass (not a Pydantic model — it is a pure service-layer type) in `services/graph_store.py`. Add `search_notes` as a new abstract method on `GraphStore` and implement it in `Neo4jGraphStore`. The method embeds-and-searches in one step from the service layer: it accepts a pre-computed query embedding, calls the HNSW index, fetches parent Note metadata, deduplicates by note (keeping the highest-scoring chunk per note), applies an optional vault filter, and returns `list[SearchResult]` sorted by score descending.

**Done when:** `search_notes(query_embedding, limit, vault_filter)` returns correctly deduplicated, sorted `SearchResult` objects. Unit tests with a mocked Neo4j session pass for: basic result, vault filter, deduplication across multiple chunks from the same note, empty result, and the `limit` parameter forwarded to `find_similar_chunks`.

## Step 2: Add `search_limit` to `BusinessConfig`

Add `search_limit: int = 10` to `BusinessConfig` in `config.py`. This field serves as the default for both the CLI command and is available for future API use. The existing `BusinessConfig.from_yaml` parsing handles it automatically.

**Done when:** `BusinessConfig` instances have a `search_limit` attribute with a default of `10`. Config unit tests pass for default value and explicit YAML override.

## Step 3: Add `get_note_by_id` to GraphStore

The `search_notes` implementation needs to fetch parent Notes for each matching Chunk by `note_id`. Add `get_note_by_id` as an abstract method and implement it in `Neo4jGraphStore`. This is a building block for `search_notes` and can be tested independently.

**Done when:** `get_note_by_id(note_id)` returns the matching `Note` or `None` if it does not exist. Unit tests cover: note found, note not found, UUID coerced to string before query.

## Step 4: Add `get_stats` to GraphStore

The stats endpoint needs counts of each node and edge type, plus a list of vault names. Add `get_stats` as an abstract method and implement it in `Neo4jGraphStore` using five separate Cypher queries.

**Done when:** `get_stats()` returns a dict with all six required keys. Unit tests cover: populated graph, empty graph, vault names sorted alphabetically.

## Step 5: Add API models and `GET /api/v1/search` endpoint

Define `SearchResult` (API response model), `SearchResponse`, `StatsResponse` as Pydantic models in `api/routes.py`. Add the `GET /search` route. The handler reads query parameters (`q`, `limit`, `vault`), fetches `app.state.embedder.embed([q])` to get the query vector, then calls `graph_store.search_notes(vector, limit, vault)`, and maps results to the response schema.

**Done when:** `GET /api/v1/search?q=...` returns HTTP 200 with a body matching `SearchResponse`. Tests for empty results, vault filtering, sorted order, limit, and missing `q` parameter (HTTP 422) all pass.

## Step 6: Add `GET /api/v1/stats` endpoint

Add the `/stats` route to `api/routes.py`. The handler calls `graph_store.get_stats()` and maps the dict to a `StatsResponse`.

**Done when:** `GET /api/v1/stats` returns HTTP 200 with a body matching `StatsResponse`. Unit tests for all fields and empty graph pass.

## Step 7: Add `kg search` CLI command

Add the `search` command to `cli.py` with a positional `query` argument and `--limit`, `--vault`, `--threshold`, and `--config` options. The `--limit` option defaults to `business.search_limit`. On success, display results in a Rich table. On no results, print `"No results found."` and exit 0.

**Done when:** `kg search "query"` exits 0, prints a Rich table with columns Score, Note Title, Vault, Heading, and Snippet. `kg search "query" --vault myvault` restricts results. CLI error-path tests pass.
