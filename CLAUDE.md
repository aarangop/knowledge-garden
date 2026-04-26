# Knowledge Garden

Consolidates multiple Obsidian vaults into a single, semantically-linked knowledge base. Ingests markdown notes, preserves explicit wikilinks, discovers semantic relationships via embeddings, and exports a unified flat vault with cross-references.

## Development Workflow

This project uses **Spec-Driven Development (SDD)** with TDD. Read `AGENTS.md` for the full workflow.

- **Specs before code.** Every change flows through `specifications/XX_name/` first.
- **Frozen specs are immutable.** Amendments get a new spec number.
- **TDD is mandatory.** Tests written before implementation (red → green → refactor).
- **Four agent roles:** Architect, Test Writer, Executor, Auditor. See `agents/` for prompts.

## Tech Stack

- Python 3.14, managed with `uv`
- FastAPI (async API)
- Neo4j 5.11+ (graph + vector search via HNSW)
- Together AI (embeddings + GLM for LLM tasks)
- httpx (async HTTP client)
- Pydantic v2 (models, settings, API schemas)
- pytest + pytest-asyncio (TDD)

## Key Commands

```bash
uv sync                                          # install dependencies
uv run uvicorn knowledge_garden.main:app --reload # run the API
uv run pytest tests/ -v -m unit                   # run unit tests
uv run pytest tests/ -v -m integration            # run integration tests
uv run ruff check src/ tests/                     # lint
uv run mypy src/                                  # type check
```

## Project Structure

```
specifications/     # Numbered spec folders (intent, roadmap, contract, tasks, audit)
agents/             # Agent prompt files (architect, test-writer, executor, auditor)
src/knowledge_garden/
  config.py         # Pydantic Settings from config.yaml
  main.py           # FastAPI app with lifespan
  models/           # Domain models (Note, Chunk, Vault)
  api/              # Route handlers
  services/         # Business logic (parser, chunker, embedder, graph store, linker, exporter)
  utils/            # Helpers
tests/              # Mirrors src structure, fixtures in tests/fixtures/
```
