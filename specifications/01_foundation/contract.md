# Contract: Foundation

## 1. Configuration

### 1.1 Config Model

File: `src/knowledge_garden/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import BaseModel, Field
from pathlib import Path

class VaultConfig(BaseModel):
    name: str
    path: str

class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "knowledge-garden"
    database: str = "neo4j"

class TogetherAIConfig(BaseModel):
    api_key: str  # from env: TOGETHER_API_KEY
    base_url: str = "https://api.together.xyz/v1"

class EmbeddingConfig(BaseModel):
    provider: str = "together"
    model: str = "togethercomputer/m2-bert-80M-8k-retrieval"
    dimension: int = 768
    batch_size: int = 64

class LLMConfig(BaseModel):
    provider: str = "together"
    model: str = "THUDM/glm-4-9b-chat"
    max_tokens: int = 1024
    temperature: float = 0.3

class ChunkingConfig(BaseModel):
    max_chunk_size: int = 1000
    min_chunk_size: int = 100

class LinkingConfig(BaseModel):
    threshold: float = 0.7
    max_neighbors: int = 20

class ExportConfig(BaseModel):
    output_dir: str = "./output"

class Config(BaseSettings):
    vaults: list[VaultConfig] = []
    neo4j: Neo4jConfig = Neo4jConfig()
    together_ai: TogetherAIConfig
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    linking: LinkingConfig = LinkingConfig()
    export: ExportConfig = ExportConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load config from a YAML file, with env var overrides."""
        ...
```

### 1.2 Config Tests

File: `tests/test_config.py`

| Test | Description | Edge Cases |
|------|-------------|------------|
| `test_config_from_yaml` | Load a valid config.yaml, verify all fields populated | |
| `test_config_env_override` | Set `TOGETHER_API_KEY` env var, verify it populates `together_ai.api_key` | |
| `test_config_defaults` | Load minimal YAML (only required fields), verify defaults are applied | |
| `test_config_missing_api_key` | Omit API key from both YAML and env → `ValidationError` | Missing required field |
| `test_config_invalid_yaml` | Malformed YAML file → clear error | Bad input |
| `test_config_vault_list` | YAML with 3 vaults → list of 3 `VaultConfig` objects | Empty vault list |

Fixture: `tests/fixtures/config_valid.yaml`, `tests/fixtures/config_minimal.yaml`

---

## 2. Domain Models

### 2.1 Models

File: `src/knowledge_garden/models/note.py`

```python
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class Vault(BaseModel):
    """Represents a source Obsidian vault."""
    name: str
    path: str  # absolute path to vault root

class Note(BaseModel):
    """A single Obsidian note, parsed from a .md file."""
    id: UUID = Field(default_factory=uuid4)
    title: str                          # filename without .md
    content: str                        # raw markdown content
    vault: str                          # source vault name
    original_path: str                  # relative path within vault
    outgoing_links: list[str] = []      # raw wikilink targets (unresolved)
    resolved_links: list[UUID] = []     # resolved Note IDs after link resolution

class Chunk(BaseModel):
    """A semantic segment of a Note."""
    id: UUID = Field(default_factory=uuid4)
    note_id: UUID                       # parent Note
    content: str                        # chunk text
    heading_context: str = ""           # nearest heading above this chunk
    index: int                          # position within the note (0-based)
    embedding: list[float] | None = None
```

### 2.2 Model Tests

File: `tests/test_models.py`

| Test | Description | Edge Cases |
|------|-------------|------------|
| `test_note_default_id` | Create Note without explicit id → UUID is auto-generated | |
| `test_note_unique_ids` | Two Notes created without explicit id → different UUIDs | |
| `test_note_serialization` | Note → `model_dump()` → dict with all fields | UUID serializes to string |
| `test_note_required_fields` | Omit `title` → `ValidationError` | Missing required fields |
| `test_note_empty_links_default` | Create Note without links → empty lists | |
| `test_chunk_requires_note_id` | Create Chunk without `note_id` → `ValidationError` | |
| `test_chunk_embedding_optional` | Create Chunk without embedding → `None` | |
| `test_chunk_embedding_accepts_floats` | Create Chunk with embedding list → stored correctly | |
| `test_vault_model` | Create Vault with name and path → fields accessible | |

---

## 3. Abstract Interfaces

### 3.1 EmbeddingService

File: `src/knowledge_garden/services/embedder.py`

```python
from abc import ABC, abstractmethod

class EmbeddingService(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...
```

### 3.2 GraphStore

File: `src/knowledge_garden/services/graph_store.py`

```python
from abc import ABC, abstractmethod
from knowledge_garden.models.note import Note, Chunk

class GraphStore(ABC):
    """Abstract graph storage backend."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create indexes, constraints, vector indexes."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    async def upsert_note(self, note: Note) -> None:
        """Insert or update a Note node."""
        ...

    @abstractmethod
    async def upsert_chunk(self, chunk: Chunk) -> None:
        """Insert or update a Chunk node with HAS_CHUNK edge to parent Note."""
        ...

    @abstractmethod
    async def create_link(self, from_note_id, to_note_id, rel_type: str) -> None:
        """Create a directed relationship between two Notes.
        rel_type: LINKS_TO | RELATED_TO"""
        ...

    @abstractmethod
    async def create_similarity(self, chunk_a_id, chunk_b_id, score: float) -> None:
        """Create a SIMILAR_TO edge between two chunks with a similarity score."""
        ...

    @abstractmethod
    async def find_similar_chunks(
        self, embedding: list[float], limit: int = 20, threshold: float = 0.7
    ) -> list[tuple[Chunk, float]]:
        """Vector similarity search via HNSW index. Returns (chunk, score) pairs."""
        ...

    @abstractmethod
    async def get_note_relationships(self, note_id) -> dict:
        """Return all LINKS_TO and RELATED_TO targets for a Note."""
        ...

    @abstractmethod
    async def get_all_notes(self) -> list[Note]:
        """Return all Note nodes."""
        ...

    @abstractmethod
    async def get_chunks_for_note(self, note_id) -> list[Chunk]:
        """Return all chunks belonging to a note, ordered by index."""
        ...
```

### 3.3 Interface Tests

File: `tests/test_interfaces.py`

| Test | Description |
|------|-------------|
| `test_embedding_service_is_abstract` | Instantiating `EmbeddingService()` directly raises `TypeError` |
| `test_embedding_service_requires_embed` | Subclass without `embed()` → `TypeError` |
| `test_embedding_service_requires_dimension` | Subclass without `dimension()` → `TypeError` |
| `test_graph_store_is_abstract` | Instantiating `GraphStore()` directly raises `TypeError` |
| `test_graph_store_requires_all_methods` | Subclass missing any abstract method → `TypeError` |
| `test_graph_store_complete_subclass` | Subclass implementing all methods → instantiates successfully |

---

## 4. Docker Compose

### 4.1 File Deliverables

| File | Location | Purpose |
|------|----------|---------|
| `docker-compose.yml` | project root | Orchestrates neo4j and api services |
| `Dockerfile` | project root | Builds the API image |
| `.env.example` | project root | Documents required environment variables |

### 4.2 `.env.example` Contents

```
# Copy to .env and fill in real values before running docker compose up
TOGETHER_API_KEY=your_together_ai_api_key_here
```

### 4.3 `Dockerfile` Specification

Base image: `ghcr.io/astral-sh/uv:python3.14-slim`

Steps:
1. Set `WORKDIR /app`
2. Copy `pyproject.toml`, `uv.lock`, and `uv.toml` (if present) first to leverage layer caching
3. Run `uv sync --frozen --no-dev` to install production dependencies
4. Copy `src/` into the image
5. Set `CMD ["uv", "run", "uvicorn", "knowledge_garden.main:app", "--host", "0.0.0.0", "--port", "8000"]`

The image must not embed `config.yaml` — it is mounted at runtime via a volume.

### 4.4 `docker-compose.yml` Service Definitions

#### neo4j service

| Key | Value |
|-----|-------|
| Image | `neo4j:5.11` |
| Container name | `knowledge-garden-neo4j` |
| Bolt port | `7687:7687` |
| Browser port | `7474:7474` |
| `NEO4J_AUTH` | `neo4j/knowledge-garden` |
| `NEO4J_PLUGINS` | `["apoc","graph-data-science"]` |
| `NEO4J_dbms_security_procedures_unrestricted` | `apoc.*,gds.*` |
| Named volume | `neo4j_data` mounted at `/data` |
| Healthcheck command | `wget -O- http://localhost:7474 \|\| exit 1` |
| Healthcheck interval | `10s` |
| Healthcheck timeout | `5s` |
| Healthcheck retries | `10` |

#### api service

| Key | Value |
|-----|-------|
| Build context | `.` (project root, uses `Dockerfile`) |
| Container name | `knowledge-garden-api` |
| Port | `8000:8000` |
| Depends on | `neo4j` (condition: `service_healthy`) |
| `env_file` | `.env` |
| Volume (config) | `./config.yaml:/app/config.yaml:ro` |

The `TOGETHER_API_KEY` environment variable is injected from `.env` via `env_file`. No secrets are baked into the compose file.

#### Named volumes

```yaml
volumes:
  neo4j_data:
```

### 4.5 Shell / Manual Tests

These are smoke tests run manually (not pytest). They verify the compose stack works end-to-end.

| Step | Command | Expected outcome |
|------|---------|-----------------|
| Start stack | `docker compose up -d` | Exits 0; both containers start |
| Neo4j browser | `curl -s -o /dev/null -w "%{http_code}" http://localhost:7474` | Returns `200` |
| API health | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health` | Returns `200` |
| Teardown | `docker compose down -v` | Exits 0; containers and `neo4j_data` volume removed |

---

## 5. Neo4j Graph Store

### 5.1 Implementation

File: `src/knowledge_garden/services/neo4j_store.py`

```python
from neo4j import AsyncGraphDatabase, AsyncDriver
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.models.note import Note, Chunk
from knowledge_garden.config import Neo4jConfig, EmbeddingConfig

class Neo4jGraphStore(GraphStore):
    """Neo4j implementation using async driver and vector indexes.

    Initialization creates:
    - Uniqueness constraint on Note.id
    - Uniqueness constraint on Chunk.id
    - Vector index on Chunk.embedding (cosine, dimension from config)

    All mutations use MERGE for idempotency.
    """

    def __init__(self, neo4j_config: Neo4jConfig, embedding_config: EmbeddingConfig):
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password),
        )
        self._database = neo4j_config.database
        self._embedding_dim = embedding_config.dimension

    async def initialize(self) -> None:
        """Create constraints and vector index."""
        ...

    async def close(self) -> None:
        """Close the Neo4j driver."""
        await self._driver.close()

    # ... all other GraphStore methods
```

Key Cypher patterns:

```cypher
-- Uniqueness constraints
CREATE CONSTRAINT note_id_unique IF NOT EXISTS FOR (n:Note) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;

-- Vector index (HNSW)
CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {indexConfig: {
    `vector.dimensions`: $dimension,
    `vector.similarity_function`: 'cosine'
}};

-- Upsert note
MERGE (n:Note {id: $id})
SET n.title = $title, n.content = $content, n.vault = $vault, n.original_path = $original_path;

-- Upsert chunk with HAS_CHUNK edge
MERGE (c:Chunk {id: $chunk_id})
SET c.content = $content, c.heading_context = $heading_context,
    c.index = $index, c.embedding = $embedding
WITH c
MATCH (n:Note {id: $note_id})
MERGE (n)-[:HAS_CHUNK]->(c);

-- Vector similarity search (uses HNSW index)
CALL db.index.vector.queryNodes('chunk_embeddings', $limit, $embedding)
YIELD node, score
WHERE score >= $threshold
RETURN node, score;
```

### 5.2 Neo4j Tests

File: `tests/test_neo4j_store.py`

These are **integration tests** (require a running Neo4j instance).

| Test | Marker | Description | Edge Cases |
|------|--------|-------------|------------|
| `test_initialize_creates_constraints` | integration | After `initialize()`, query constraints → Note and Chunk unique constraints exist | |
| `test_initialize_creates_vector_index` | integration | After `initialize()`, query indexes → `chunk_embeddings` vector index exists | |
| `test_initialize_idempotent` | integration | Call `initialize()` twice → no error | |
| `test_upsert_note_creates_node` | integration | Upsert a Note → query by id → node exists with correct properties | |
| `test_upsert_note_updates_existing` | integration | Upsert same Note id with different title → title updated | |
| `test_upsert_chunk_creates_node_and_edge` | integration | Upsert a Chunk → HAS_CHUNK edge exists to parent Note | |
| `test_create_link` | integration | Create LINKS_TO between two Notes → edge exists | |
| `test_close_cleans_up` | integration | After `close()`, driver is closed | |

Fixture: `conftest.py` should provide a `neo4j_store` fixture that initializes a test database and cleans up after each test.

---

## 6. Together AI Embedder

### 6.1 Implementation

File: `src/knowledge_garden/services/together_embedder.py`

```python
import httpx
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.config import TogetherAIConfig, EmbeddingConfig

class TogetherAIEmbedder(EmbeddingService):
    """Embedding via Together AI API."""

    def __init__(self, together_config: TogetherAIConfig, embedding_config: EmbeddingConfig):
        self._client = httpx.AsyncClient(
            base_url=together_config.base_url,
            headers={"Authorization": f"Bearer {together_config.api_key}"},
            timeout=60.0,
        )
        self._model = embedding_config.model
        self._dimension = embedding_config.dimension
        self._batch_size = embedding_config.batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via Together AI /embeddings endpoint. Batches internally."""
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = await self._client.post(
                "/embeddings",
                json={"model": self._model, "input": batch},
            )
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend([item["embedding"] for item in data["data"]])
        return all_embeddings

    def dimension(self) -> int:
        return self._dimension

    async def close(self) -> None:
        await self._client.aclose()
```

### 6.2 Embedder Tests

File: `tests/test_together_embedder.py`

**Unit tests** mock httpx. **Integration tests** hit the real API.

| Test | Marker | Description | Edge Cases |
|------|--------|-------------|------------|
| `test_embed_single_text` | unit | Mock httpx → embed(["hello"]) → returns 1 vector of correct dimension | |
| `test_embed_batch` | unit | Mock httpx → embed(["a", "b", "c"]) → returns 3 vectors | |
| `test_embed_batching_splits_large_input` | unit | Input of 100 texts, batch_size=64 → 2 HTTP calls made | |
| `test_embed_empty_list` | unit | embed([]) → returns [] | Empty input |
| `test_embed_api_error_propagates` | unit | Mock httpx 500 → `httpx.HTTPStatusError` raised | API failure |
| `test_dimension_returns_configured` | unit | dimension() == config.dimension | |
| `test_close_closes_client` | unit | After close(), client is closed | |
| `test_embed_real_api` | integration | Real Together AI call → vectors of correct dimension, normalized | |

Fixture: `mock_together_response` in conftest.py — returns a valid Together AI embeddings response JSON.

---

## 7. FastAPI Application

### 7.1 Implementation

File: `src/knowledge_garden/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from knowledge_garden.config import Config
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.together_embedder import TogetherAIEmbedder

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, instantiate services, initialize graph store.
    Shutdown: close connections."""
    config = Config.from_yaml("config.yaml")

    graph_store = Neo4jGraphStore(config.neo4j, config.embedding)
    await graph_store.initialize()

    embedder = TogetherAIEmbedder(config.together_ai, config.embedding)

    app.state.config = config
    app.state.graph_store = graph_store
    app.state.embedder = embedder

    yield

    await embedder.close()
    await graph_store.close()

app = FastAPI(title="Knowledge Garden", version="0.1.0", lifespan=lifespan)

@app.get("/api/v1/health")
async def health():
    """Returns health status including Neo4j and Together AI connectivity."""
    # Verify Neo4j with a lightweight query
    # Verify Together AI with a test embed (optional, can just check config)
    return {"status": "healthy", "neo4j": "connected", "together_ai": "configured"}
```

### 7.2 API Tests

File: `tests/test_api.py`

| Test | Marker | Description | Edge Cases |
|------|--------|-------------|------------|
| `test_health_endpoint` | unit | Mock services → GET /api/v1/health → 200 with status fields | |
| `test_health_response_schema` | unit | Response contains `status`, `neo4j`, `together_ai` keys | |
| `test_app_startup_initializes_services` | unit | After startup, `app.state.graph_store` and `app.state.embedder` exist | |

Fixture: Use FastAPI `TestClient` with overridden lifespan that injects mock services.

---

## 8. Test Fixtures (conftest.py)

File: `tests/conftest.py`

```python
import pytest
from unittest.mock import AsyncMock
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore

@pytest.fixture
def mock_embedder():
    """Mock EmbeddingService that returns deterministic vectors."""
    embedder = AsyncMock(spec=EmbeddingService)
    embedder.dimension.return_value = 768
    embedder.embed.return_value = [[0.1] * 768]  # single vector
    return embedder

@pytest.fixture
def mock_graph_store():
    """Mock GraphStore for unit testing."""
    store = AsyncMock(spec=GraphStore)
    return store

def mock_together_response(num_embeddings: int = 1, dimension: int = 768) -> dict:
    """Generate a mock Together AI /embeddings response."""
    return {
        "data": [
            {"embedding": [0.1] * dimension, "index": i}
            for i in range(num_embeddings)
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }
```

Fixture files:
- `tests/fixtures/config_valid.yaml` — full config with all sections
- `tests/fixtures/config_minimal.yaml` — only required fields (together_ai.api_key)
