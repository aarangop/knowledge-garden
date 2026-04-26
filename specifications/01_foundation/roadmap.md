# Roadmap: Foundation

## Steps

### 1. Configuration system
Load settings from `config.yaml` with environment variable overrides (especially for API keys). Validate with Pydantic Settings.
**Done when:** `Config` class loads from YAML, reads `TOGETHER_API_KEY` from env, and validation errors are clear.

### 2. Domain models
Define `Vault`, `Note`, and `Chunk` as Pydantic models with all fields specified in the contract.
**Done when:** Models can be instantiated, serialized to dict/JSON, and have sensible defaults.

### 3. Abstract interfaces
Define `EmbeddingService` and `GraphStore` as abstract base classes with all method signatures from the contract.
**Done when:** ABCs exist with all specified methods. Attempting to instantiate them directly raises `TypeError`.

### 4. Docker Compose setup
Create a `docker-compose.yml` at the project root that starts Neo4j 5.11 and the API service, a `Dockerfile` for the API image, and a `.env.example` listing required environment variables.
**Done when:** A `docker-compose.yml` at the project root starts both Neo4j and the API service; `docker compose up` succeeds, Neo4j browser is reachable at `localhost:7474`, and `GET localhost:8000/api/v1/health` returns 200.

### 5. Neo4j graph store implementation
Implement `Neo4jGraphStore` with connection management, `initialize()` for constraints and vector index creation, and the `close()` lifecycle method.
**Done when:** Connects to a running Neo4j instance, creates constraints and vector index, and can be cleanly shut down.

### 6. Together AI embedder implementation
Implement `TogetherAIEmbedder` with async httpx client, batched embedding calls, and proper client lifecycle.
**Done when:** Can embed a batch of strings via Together AI API and return vectors of the correct dimension.

### 7. FastAPI application with lifespan
Wire up `main.py` with lifespan context manager that instantiates services, a health endpoint, and router registration.
**Done when:** App starts, `/api/v1/health` returns 200 with Neo4j and Together AI status, app shuts down cleanly.
