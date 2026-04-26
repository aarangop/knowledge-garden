# Intent: CLI and Pipeline Extraction

## What

Phase 03 introduces a command-line interface (`kg`) and extracts the ingest pipeline logic from the API layer into a standalone, reusable service. The `POST /api/v1/ingest` endpoint is removed; ingestion becomes a CLI-only concern.

## Why

Vault ingestion is a long-running batch job that can take minutes on large vaults. Coupling it to an HTTP request/response cycle creates real problems: timeouts, no live progress feedback, and a stateful server managing a write-heavy operation. The API server should remain stateless, serving reads (search, retrieval) only.

The pipeline logic in `routes.py` is also currently untestable in isolation — it is entangled with FastAPI `Request` objects and app state. Extracting it into `IngestPipeline` gives that logic clean inputs and outputs, a distinct test surface, and a path to reuse from any entry point (CLI today, batch runner tomorrow).

## User-visible behavior

- `kg ingest <vault_name>` — runs the full ingest pipeline with a live progress bar showing each note as it is processed. Prints a summary table on completion.
- `kg notes [--vault <name>]` — lists all notes currently in the graph, optionally filtered by vault, as a rich table.
- `kg status` — prints aggregate counts (total notes, total chunks) broken down by vault.
- `kg` is available as a system command after `uv sync` because it is registered as a `[project.scripts]` entry point.

## Scope of this phase

1. Extract the ingest pipeline into `src/knowledge_garden/services/pipeline.py` (`IngestPipeline` class).
2. Remove `POST /api/v1/ingest` from `routes.py` and delete `tests/test_ingest_api.py`.
3. Add unit tests for `IngestPipeline` in `tests/test_pipeline.py`.
4. Implement `src/knowledge_garden/cli.py` using `typer` and `rich`, with three commands: `ingest`, `notes`, `status`.
5. Register `kg` as a `[project.scripts]` entry point in `pyproject.toml`.
6. Add `typer` and `rich` as runtime dependencies in `pyproject.toml`.

## Out of scope

- Semantic search endpoint.
- Wikilink resolution (mapping `outgoing_links` to Note IDs).
- Export / unified vault generation.
- Incremental ingestion (change detection).
- Single-note ingest command.
- `GET /api/v1/notes` is not changed; it stays in the API.

## Open questions

- None. All behavior is fully specified.
