# Tasks: Foundation

## Configuration

- [x] Create `tests/fixtures/config_valid.yaml` and `tests/fixtures/config_minimal.yaml`
- [x] Write tests for Config (`tests/test_config.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/config.py`
- [x] Verify tests pass — green phase (6/6 passing)

## Domain Models

- [x] Write tests for Note, Chunk, Vault (`tests/test_models.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/models/note.py`
- [x] Verify tests pass — green phase (9/9 passing)

## Abstract Interfaces

- [x] Write tests for EmbeddingService and GraphStore ABCs (`tests/test_interfaces.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/services/embedder.py` (abstract only)
- [x] Implement `src/knowledge_garden/services/graph_store.py` (abstract only)
- [x] Verify tests pass — green phase (6/6 passing)

## Docker Compose Setup

- [x] Create `.env.example` at the project root with `TOGETHER_API_KEY` placeholder
- [x] Create `Dockerfile` at the project root using `ghcr.io/astral-sh/uv:python3.14-slim`, installing deps with `uv sync --frozen --no-dev`, and setting the uvicorn CMD
- [x] Create `docker-compose.yml` at the project root with `neo4j` and `api` service definitions as specified in contract section 4.4
- [x] Verify `docker compose config` exits 0 (validate compose file syntax)
- [x] Run `docker compose up -d` and confirm both containers start
- [x] Verify Neo4j browser reachable: `curl -s -o /dev/null -w "%{http_code}" http://localhost:7474` returns `200`
- [x] Verify API health: `curl -s http://localhost:8000/api/v1/health` returns `{"status":"healthy","neo4j":"connected","together_ai":"configured"}`
- [x] Run `docker compose down -v` and confirm it exits 0

## Neo4j Graph Store

- [x] Write integration tests for Neo4jGraphStore (`tests/test_neo4j_store.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/services/neo4j_store.py`
- [x] Verify integration tests pass — green phase (8/8 passing)

## Together AI Embedder

- [x] Write unit tests for TogetherAIEmbedder (`tests/test_together_embedder.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/services/together_embedder.py`
- [x] Verify unit tests pass — green phase (7/7 unit passing, 1 integration skipped — needs `TOGETHER_API_KEY`)

## FastAPI Application

- [x] Write `tests/conftest.py` with shared fixtures (mock_embedder, mock_graph_store, mock_together_response)
- [x] Write tests for health endpoint and app startup (`tests/test_api.py`) — red phase
- [x] Verify tests fail
- [x] Implement `src/knowledge_garden/main.py`
- [x] Verify tests pass — green phase (3/3 passing)

## Final Verification

- [x] Run full test suite: `uv run pytest tests/ -v --tb=short -m unit`
- [x] All unit tests pass (31/31)
- [x] Run integration tests: `uv run pytest tests/ -v --tb=short -m integration` — 8/8 passing (Neo4j via Docker)
- [x] App starts and `/api/v1/health` returns 200 (verified via `docker compose up`)
