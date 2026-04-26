# Knowledge Garden — System Specification

## 1. High-Level Intent

Knowledge Garden is a local-first system that consolidates multiple Obsidian vaults into a single, semantically-linked knowledge base. It ingests markdown notes from any number of vaults, preserves explicit relationships (wikilinks), discovers implicit relationships through semantic similarity, and exports a unified flat vault where every note is enriched with cross-references — both original and discovered.

The system solves a specific problem: years of accumulated knowledge spread across vaults that were structured differently, tagged inconsistently, and organized under varying philosophies. Rather than manually reconciling these, Knowledge Garden treats the content and its links as the source of truth, discards the organizational scaffolding (folder hierarchies, inconsistent metadata), and rebuilds a connected knowledge graph from scratch.

**Expected behavior:** Point the system at N vault directories. It parses every note, builds a graph of explicit links, chunks and embeds the content, discovers semantic neighbors across vault boundaries, and exports a new Obsidian vault where every note carries a `## References` section with wikilinks to related notes — both those that were explicitly linked and those discovered via similarity.

**Expected outcome:** A flat Obsidian vault (~3000-4000 notes) that can be opened in Obsidian and navigated through its graph view, where cross-vault knowledge is surfaced through links that didn't previously exist.

---

## 2. Architecture Critique & Design Decisions

Before the roadmap, here are the key design decisions, including responses to the open questions and critiques of the original proposal.

### 2.1 Chunks vs Notes as Graph Units

**Decision: Both, as a two-level hierarchy.**

Notes are the primary nodes — they represent the unit of knowledge the author created, and they're what Obsidian links reference. Chunks are sub-nodes used for embedding precision, since a long note about multiple topics would produce a muddled embedding if embedded whole.

The graph has two node types:
- `Note` — represents a full markdown file, carries metadata (title, source vault, original path)
- `Chunk` — represents a semantic segment of a note, carries the embedding vector

Relationships:
- `Note -[HAS_CHUNK]-> Chunk` (structural)
- `Note -[LINKS_TO]-> Note` (explicit wikilinks from the source vault)
- `Chunk -[SIMILAR_TO]-> Chunk` (discovered via semantic similarity)
- `Note -[RELATED_TO]-> Note` (derived: if chunks from two notes are SIMILAR_TO each other, their parent notes are RELATED_TO each other)

At export time, we operate at the Note level. A note's references section includes all `LINKS_TO` and `RELATED_TO` notes, deduplicated.

### 2.2 Graph DB + Embeddings: One Database, Not Two

**Decision: Neo4j handles both.**

Neo4j 5.11+ supports native vector indexes. You can store embedding vectors as properties on Chunk nodes and create a vector index for cosine similarity search. This eliminates the need for a separate vector database (no ChromaDB, no pgvector). One database for structure and similarity.

This is the pragmatic choice for a local system: single dependency, single data store, unified query language (Cypher). The trade-off is that Neo4j's vector search is less feature-rich than dedicated vector DBs (no HNSW tuning knobs, no metadata filtering on vector queries). For ~15K chunks this doesn't matter — performance will be fine.

### 2.3 Critique: BFS Traversal is Overcomplicated

The proposed BFS-from-random-note approach is essentially connected component detection. It works, but it conflates two concerns: parsing notes and building the graph.

**Simpler approach:** Parse all notes in a vault linearly (they're just files in a directory). During parsing, extract all wikilinks. After all notes are parsed, insert all Note nodes into Neo4j, then insert all LINKS_TO edges by resolving the extracted wikilinks. Connected components emerge naturally from the graph structure — no need to implement BFS yourself.

BFS is useful later, during semantic linking, if you want to explore neighborhoods. But for ingestion, a flat scan is simpler and equally correct.

### 2.4 Critique: LLM Summarization for Query Generation is Unnecessary

The original design proposes summarizing chunks with a small LLM to produce search queries for semantic linking. For 10K-15K chunks, this adds significant latency and compute cost with marginal benefit.

**Simpler approach:** Use the chunk embedding directly for KNN search. The embedding already captures the semantic content. To find similar chunks, query the vector index with each chunk's embedding and take the top-K nearest neighbors above a similarity threshold. No LLM needed for this step.

Reserve LLM calls for higher-value tasks:
- Deduplication resolution (when two notes from different vaults have similar titles and content, an LLM can decide if they're the same note or distinct)
- Export enrichment (optional: generating a brief summary for each note's frontmatter)

### 2.5 Missing Piece: Deduplication

Across 3-4 vaults, duplicate or near-duplicate notes are inevitable. The system needs a dedup strategy:

1. **Title-based exact match** — same filename across vaults → flag as candidate
2. **Embedding similarity** — notes whose aggregate chunk embeddings are very close (>0.92) → flag as candidate  
3. **Resolution** — for flagged candidates, either merge automatically (keep the longer/newer version) or, optionally, use an LLM to merge content

This is implemented as a step between ingestion and semantic linking.

### 2.6 Missing Piece: Link Resolution

Obsidian wikilinks are ambiguous. `[[Machine Learning]]` might match `Machine Learning.md`, `AI/Machine Learning.md`, or nothing (broken link). Link resolution must be per-vault (using Obsidian's own resolution rules: shortest path, then alphabetical), and must handle:

- Exact filename match (case-insensitive)
- Path-based links (`[[folder/note]]`)
- Alias links (`[[note|display text]]`)
- Heading links (`[[note#heading]]`) — resolve to the Note node, ignore the heading anchor
- Broken links — log and skip, don't create edges for links that don't resolve

### 2.7 Flat Vault, Minimal Metadata — Agreed

The decision to use a flat vault with minimal metadata is sound. The output notes will carry only:

```yaml
---
title: "Note Title"
source_vault: "vault-name"
garden_id: "uuid"
---
```

No tags, no complex frontmatter. The knowledge structure lives in the links, not the metadata.

### 2.8 Similarity Threshold

The default of 0.7 is reasonable for `all-MiniLM-L6-v2` (the recommended embedding model). However, this should be configurable per-run, and the system should support a `limit` parameter (default 20) to cap the number of semantic neighbors per chunk. Without a limit, popular topics will accumulate hundreds of weak connections.

---

## 3. Roadmap

Six phases, each completable in a focused working session.

### Phase 1: Foundation
Set up project structure, Neo4j connection, core data models, and FastAPI skeleton. By the end, the API starts, Neo4j is reachable, and the data model is defined.

### Phase 2: Vault Parsing & Ingestion
Build the vault parser: walk directories, parse markdown, extract wikilinks, resolve links within a vault, insert Note nodes and LINKS_TO edges into Neo4j. By the end, a vault can be ingested and its link graph queried in Neo4j.

### Phase 3: Chunking & Embedding
Implement the chunking strategy and embedding pipeline. Chunk notes, generate embeddings, store them as Chunk nodes with vector properties, create the Neo4j vector index. By the end, chunks are embedded and vector search works.

### Phase 4: Semantic Linking & Deduplication
Run KNN similarity search across all chunks, create SIMILAR_TO edges, derive RELATED_TO edges between notes, and handle cross-vault deduplication. By the end, the graph contains both explicit and discovered relationships.

### Phase 5: Knowledge Export
Generate the unified vault: for each Note, produce a markdown file with the original content and a References section containing wikilinks to all related notes. By the end, a usable Obsidian vault exists on disk.

### Phase 6: Search API & Refinement
Implement the semantic search endpoint, add status/progress reporting, and polish the API surface. By the end, the system is usable end-to-end with a clean API.

---

## 4. Contract

### 4.1 Tech Stack

| Component         | Choice                         | Rationale                              |
|--------------------|---------------------------------|----------------------------------------|
| Language           | Python 3.14                    | Latest, ecosystem, async support       |
| API Framework      | FastAPI                        | Async, type-safe, auto-docs            |
| Graph DB           | Neo4j 5.11+ (Community)        | Graph + vector search, local           |
| Neo4j Driver       | `neo4j` (async)                | Official async Python driver           |
| Embeddings         | Together AI API                | Higher quality models, existing credits |
| Embedding Model    | Configurable (via Together AI) | e.g. `togethercomputer/m2-bert-80M-8k-retrieval` or similar |
| LLM               | Together AI API (GLM)          | Dedup resolution, affordable           |
| HTTP Client        | `httpx`                        | Async HTTP for Together AI calls       |
| Markdown Parsing   | `markdown-it-py` + custom      | Wikilink extraction, frontmatter       |
| Validation         | Pydantic v2                    | Models, settings, API schemas          |
| Task Queue         | None (sync processing is fine) | <5K notes, no need for Celery          |
| Testing            | pytest + pytest-asyncio        | Standard                               |

### 4.2 Project Structure

```
knowledge-garden/
├── pyproject.toml
├── README.md
├── config.yaml                  # vault paths, neo4j connection, model settings
├── src/
│   └── knowledge_garden/
│       ├── __init__.py
│       ├── main.py              # FastAPI app, lifespan, router registration
│       ├── config.py            # Pydantic Settings, loaded from config.yaml
│       ├── models/
│       │   ├── __init__.py
│       │   ├── note.py          # Note, Chunk, Vault domain models
│       │   └── graph.py         # Relationship types, graph query results
│       ├── api/
│       │   ├── __init__.py
│       │   ├── ingest.py        # /process_vault, /process_all
│       │   ├── link.py          # /link_knowledge
│       │   ├── search.py        # /search
│       │   ├── export.py        # /export
│       │   └── schemas.py       # Request/Response Pydantic models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── vault_parser.py  # Obsidian vault parsing, wikilink extraction
│       │   ├── chunker.py       # Semantic chunking logic
│       │   ├── embedder.py      # Embedding generation (abstract + impl)
│       │   ├── graph_store.py   # Neo4j operations (abstract + impl)
│       │   ├── linker.py        # Semantic linking engine
│       │   ├── dedup.py         # Deduplication detection & resolution
│       │   └── exporter.py      # Vault export / markdown generation
│       └── utils/
│           ├── __init__.py
│           ├── markdown.py      # Markdown parsing helpers
│           └── logging.py       # Structured logging setup
└── tests/
    ├── conftest.py
    ├── fixtures/                 # Sample vault snippets for testing
    ├── test_vault_parser.py
    ├── test_chunker.py
    ├── test_embedder.py
    ├── test_graph_store.py
    ├── test_linker.py
    └── test_exporter.py
```

### 4.3 Core Interfaces (Contracts)

#### 4.3.1 Domain Models

```python
# models/note.py
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

#### 4.3.2 Embedding Service (Abstract Interface)

This preserves the pattern from the prior RAG project — an abstract interface that allows swapping embedding providers.

```python
# services/embedder.py
from abc import ABC, abstractmethod

class EmbeddingService(ABC):
    """Abstract embedding provider. Implementations can use
    Together AI, sentence-transformers, OpenAI, or any other backend."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns a list of embedding vectors."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        ...


class TogetherAIEmbedder(EmbeddingService):
    """Embedding via Together AI API. Supports any embedding model
    available on the Together platform."""

    def __init__(
        self,
        api_key: str,
        model: str = "togethercomputer/m2-bert-80M-8k-retrieval",
        base_url: str = "https://api.together.xyz/v1",
        dimension: int = 768,
        batch_size: int = 64,
    ):
        import httpx
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via Together AI /embeddings endpoint.
        Handles batching internally to respect API limits."""
        all_embeddings = []
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

#### 4.3.3 Graph Store (Abstract Interface)

```python
# services/graph_store.py
from abc import ABC, abstractmethod
from models.note import Note, Chunk

class GraphStore(ABC):
    """Abstract graph storage backend."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create indexes, constraints, vector indexes."""
        ...

    @abstractmethod
    async def upsert_note(self, note: Note) -> None:
        """Insert or update a Note node."""
        ...

    @abstractmethod
    async def upsert_chunk(self, chunk: Chunk) -> None:
        """Insert or update a Chunk node with its embedding."""
        ...

    @abstractmethod
    async def create_link(self, from_note_id, to_note_id, rel_type: str) -> None:
        """Create a directed relationship between two Notes.
        rel_type is one of: LINKS_TO, RELATED_TO"""
        ...

    @abstractmethod
    async def create_similarity(self, chunk_a_id, chunk_b_id, score: float) -> None:
        """Create a SIMILAR_TO edge between two chunks with a similarity score."""
        ...

    @abstractmethod
    async def find_similar_chunks(
        self, embedding: list[float], limit: int = 20, threshold: float = 0.7
    ) -> list[tuple[Chunk, float]]:
        """Vector similarity search. Returns (chunk, score) pairs."""
        ...

    @abstractmethod
    async def get_note_relationships(self, note_id) -> dict:
        """Return all LINKS_TO and RELATED_TO targets for a Note."""
        ...

    @abstractmethod
    async def get_all_notes(self) -> list[Note]:
        """Return all Note nodes (for export)."""
        ...

    @abstractmethod
    async def get_chunks_for_note(self, note_id) -> list[Chunk]:
        """Return all chunks belonging to a note, ordered by index."""
        ...


class Neo4jGraphStore(GraphStore):
    """Neo4j implementation using the async driver and vector indexes.

    Key Cypher patterns:
    - Vector index creation:
        CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
        FOR (c:Chunk) ON (c.embedding)
        OPTIONS {indexConfig: {
            `vector.dimensions`: 384,
            `vector.similarity_function`: 'cosine'
        }}

    - Similarity search:
        CALL db.index.vector.queryNodes('chunk_embeddings', $limit, $embedding)
        YIELD node, score
        WHERE score >= $threshold
        RETURN node, score

    - Derive RELATED_TO from SIMILAR_TO:
        MATCH (n1:Note)-[:HAS_CHUNK]->(c1:Chunk)-[s:SIMILAR_TO]->(c2:Chunk)<-[:HAS_CHUNK]-(n2:Note)
        WHERE n1 <> n2 AND s.score >= $threshold
        MERGE (n1)-[r:RELATED_TO]->(n2)
        SET r.score = max(r.score, s.score)
    """
    ...
```

#### 4.3.4 Vault Parser

```python
# services/vault_parser.py
import re
from pathlib import Path
from models.note import Note, Vault

# Wikilink regex: captures [[target]], [[target|alias]], [[target#heading]]
WIKILINK_PATTERN = re.compile(r'\[\[([^\]|#]+)(?:#[^\]|]*)??(?:\|[^\]]+)?\]\]')

class VaultParser:
    """Parses an Obsidian vault directory into Note objects.

    Responsibilities:
    - Walk the vault directory for .md files
    - Parse frontmatter (minimal: just extract title if present)
    - Extract wikilinks from content
    - Resolve wikilinks to Note IDs within the same vault
    - Skip non-note files (templates, config, .obsidian/)

    Link resolution strategy (matches Obsidian's behavior):
    1. Exact filename match (case-insensitive)
    2. If ambiguous, prefer the note in the same directory
    3. If still ambiguous, prefer shortest path
    4. Broken links are logged and skipped
    """

    def __init__(self, vault: Vault):
        self.vault = vault
        self._notes: dict[str, Note] = {}       # title_lower -> Note
        self._title_index: dict[str, list[Note]] = {}  # for ambiguity resolution

    async def parse(self) -> list[Note]:
        """Parse all .md files in the vault. Returns list of Notes
        with outgoing_links populated (unresolved strings)."""
        ...

    def resolve_links(self, notes: list[Note]) -> list[Note]:
        """Resolve outgoing_links strings to Note IDs.
        Mutates notes in place, populating resolved_links."""
        ...

    @staticmethod
    def extract_wikilinks(content: str) -> list[str]:
        """Extract wikilink targets from markdown content."""
        return WIKILINK_PATTERN.findall(content)

    @staticmethod
    def strip_frontmatter(content: str) -> tuple[dict, str]:
        """Split YAML frontmatter from body. Returns (metadata, body)."""
        ...
```

#### 4.3.5 Chunker

```python
# services/chunker.py
from models.note import Note, Chunk

class Chunker:
    """Splits notes into semantic chunks for embedding.

    Strategy: heading-aware chunking.
    1. Split on headings (##, ###, etc.) — each heading starts a new chunk.
    2. If a section exceeds max_chunk_size, split further on paragraph
       boundaries (double newline).
    3. If a paragraph still exceeds max_chunk_size, split on sentence
       boundaries.
    4. Each chunk records its nearest heading ancestor for context.

    Chunks smaller than min_chunk_size are merged with the previous chunk.

    This approach preserves the author's semantic structure (headings = topic
    boundaries) while keeping chunks within a size range suitable for embedding.
    """

    def __init__(self, max_chunk_size: int = 1000, min_chunk_size: int = 100):
        self.max_chunk_size = max_chunk_size  # characters
        self.min_chunk_size = min_chunk_size

    def chunk_note(self, note: Note) -> list[Chunk]:
        """Split a note into chunks. Returns ordered list of Chunks."""
        ...
```

#### 4.3.6 Semantic Linker

```python
# services/linker.py

class SemanticLinker:
    """Discovers semantic relationships between chunks across the entire graph.

    Algorithm:
    1. Iterate through all Chunk nodes that have embeddings.
    2. For each chunk, query the vector index for KNN neighbors.
    3. Filter: exclude chunks from the same Note (intra-note similarity is noise).
    4. For neighbors above the threshold, create SIMILAR_TO edges.
    5. After all chunks are processed, derive RELATED_TO edges between Notes
       by aggregating SIMILAR_TO edges (a Note pair gets RELATED_TO if any of
       their chunks are SIMILAR_TO, score = max chunk similarity).

    Batching: process chunks in batches of 100 to avoid memory pressure.
    Idempotency: uses MERGE for edge creation, safe to re-run.
    """

    def __init__(
        self,
        graph_store: GraphStore,
        threshold: float = 0.7,
        max_neighbors: int = 20,
    ):
        self.graph_store = graph_store
        self.threshold = threshold
        self.max_neighbors = max_neighbors

    async def link_all(self) -> dict:
        """Run semantic linking across all chunks.
        Returns stats: {chunks_processed, edges_created, notes_linked}."""
        ...

    async def derive_note_relationships(self) -> int:
        """Derive RELATED_TO edges between Notes from SIMILAR_TO edges
        between their chunks. Returns number of RELATED_TO edges created."""
        ...
```

#### 4.3.7 Exporter

```python
# services/exporter.py
from pathlib import Path

class VaultExporter:
    """Exports the knowledge graph as a flat Obsidian vault.

    For each Note in the graph:
    1. Write the original content (stripped of old frontmatter).
    2. Prepend minimal frontmatter (title, source_vault, garden_id).
    3. Append a ## References section with wikilinks to:
       - All LINKS_TO notes (explicit, original links)
       - All RELATED_TO notes (discovered via semantic similarity)
       References are grouped by type and sorted by relevance score
       (for RELATED_TO) or alphabetically (for LINKS_TO).
    4. Write to output_dir/{title}.md

    Filename conflicts (two notes from different vaults with the same title)
    are resolved by appending the source vault name: {title} ({vault}).md
    """

    def __init__(self, graph_store: GraphStore, output_dir: str):
        self.graph_store = graph_store
        self.output_dir = Path(output_dir)

    async def export(self) -> dict:
        """Export all notes. Returns stats: {notes_exported, links_written}."""
        ...

    def _build_references_section(self, links_to: list, related_to: list) -> str:
        """Build the ## References markdown section."""
        ...
```

#### 4.3.8 API Schemas

```python
# api/schemas.py
from pydantic import BaseModel, Field

class ProcessVaultRequest(BaseModel):
    vault_path: str
    vault_name: str | None = None  # defaults to directory name

class ProcessVaultResponse(BaseModel):
    vault_name: str
    notes_parsed: int
    links_resolved: int
    chunks_created: int
    chunks_embedded: int

class LinkKnowledgeRequest(BaseModel):
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    max_neighbors: int = Field(default=20, ge=1, le=100)

class LinkKnowledgeResponse(BaseModel):
    chunks_processed: int
    similarity_edges_created: int
    note_relationships_derived: int

class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=20, ge=1, le=100)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)

class SearchResult(BaseModel):
    note_title: str
    chunk_content: str
    heading_context: str
    score: float
    source_vault: str

class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str

class ExportRequest(BaseModel):
    output_dir: str
    include_explicit_links: bool = True
    include_semantic_links: bool = True

class ExportResponse(BaseModel):
    notes_exported: int
    links_written: int
    output_dir: str
```

#### 4.3.9 API Endpoints

```python
# main.py — endpoint summary

POST /api/v1/ingest/vault          # Process a single vault
POST /api/v1/ingest/all            # Process all vaults from config
POST /api/v1/link                  # Run semantic linking
POST /api/v1/search                # Semantic search
POST /api/v1/export                # Export to vault
GET  /api/v1/stats                 # Graph stats (note count, edge count, etc.)
GET  /api/v1/health                # Health check (Neo4j connectivity)
```

### 4.4 Configuration

```yaml
# config.yaml
vaults:
  - name: "personal-2021"
    path: "/path/to/vault1"
  - name: "work-2023"
    path: "/path/to/vault2"
  - name: "research"
    path: "/path/to/vault3"

neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "knowledge-garden"
  database: "neo4j"

together_ai:
  api_key: "${TOGETHER_API_KEY}"      # loaded from env var
  base_url: "https://api.together.xyz/v1"

embedding:
  provider: "together"                # backed by Together AI
  model: "togethercomputer/m2-bert-80M-8k-retrieval"  # or any Together-hosted embedding model
  dimension: 768
  batch_size: 64

llm:
  provider: "together"
  model: "THUDM/glm-4-9b-chat"       # GLM via Together AI, cost-effective
  max_tokens: 1024
  temperature: 0.3                    # low temp for deterministic dedup decisions

chunking:
  max_chunk_size: 1000    # characters
  min_chunk_size: 100

linking:
  threshold: 0.7
  max_neighbors: 20

export:
  output_dir: "/path/to/knowledge-garden-vault"
```

### 4.5 Key Design Patterns

**Dependency Injection via FastAPI lifespan.** Services are instantiated at startup in the lifespan context manager and stored in `app.state`. Route handlers access them via `request.app.state`. This keeps services testable (inject mocks) without a DI framework.

**Abstract interfaces for swappable backends.** `EmbeddingService` and `GraphStore` are abstract base classes. The concrete implementations (`TogetherAIEmbedder`, `Neo4jGraphStore`) are specified in config and instantiated at startup. Adding a new backend (e.g., local sentence-transformers, or a different graph store) means implementing the interface — no changes to business logic.

**Idempotent operations.** All graph mutations use `MERGE` (upsert) rather than `CREATE`. Reprocessing a vault updates existing nodes rather than creating duplicates. This is critical for iterative refinement.

**Batch processing with progress reporting.** Long operations (embedding, linking) process items in configurable batches and yield progress updates. The API can report progress via polling or SSE (stretch goal).

---

## 5. Tasks

### Phase 1: Foundation

- [ ] Initialize project with `pyproject.toml` (dependencies: fastapi, uvicorn, neo4j, httpx, pydantic, pyyaml, markdown-it-py); requires Python 3.14
- [ ] Create project directory structure (`src/knowledge_garden/`, `tests/`, etc.)
- [ ] Implement `config.py` — Pydantic Settings class loading from `config.yaml`, with Together AI API key from env var
- [ ] Implement domain models in `models/note.py` (Vault, Note, Chunk)
- [ ] Implement `graph_store.py` — abstract `GraphStore` interface
- [ ] Implement `Neo4jGraphStore` — connection setup, `initialize()` with constraints and vector index creation
- [ ] Implement `embedder.py` — abstract `EmbeddingService` interface
- [ ] Implement `TogetherAIEmbedder` — async httpx client calling Together AI /embeddings endpoint
- [ ] Implement `main.py` — FastAPI app with lifespan (instantiate services, manage httpx client lifecycle), health endpoint
- [ ] Write `tests/conftest.py` with fixtures for mock graph store and embedder
- [ ] Verify: app starts, `/health` returns OK, Neo4j is reachable, Together AI embedding call succeeds

### Phase 2: Vault Parsing & Ingestion

- [ ] Implement `VaultParser.parse()` — walk directory, read .md files, extract frontmatter and body
- [ ] Implement `VaultParser.extract_wikilinks()` — regex extraction of `[[target]]` variants
- [ ] Implement `VaultParser.resolve_links()` — resolve wikilink strings to Note IDs within the vault
- [ ] Implement `VaultParser.strip_frontmatter()` — split YAML frontmatter from body
- [ ] Add skip logic for `.obsidian/`, template folders, non-.md files
- [ ] Implement `GraphStore.upsert_note()` in Neo4j — create/update Note nodes
- [ ] Implement `GraphStore.create_link()` in Neo4j — create LINKS_TO edges
- [ ] Implement `POST /api/v1/ingest/vault` endpoint — accepts vault path, runs parser, stores in Neo4j
- [ ] Implement `POST /api/v1/ingest/all` endpoint — processes all vaults from config sequentially
- [ ] Create test fixtures: sample vault directory with 5-10 interconnected .md files
- [ ] Write tests for wikilink extraction (all variants: basic, alias, heading, path)
- [ ] Write tests for link resolution (exact match, ambiguous, broken)
- [ ] Write integration test: ingest sample vault → verify Note nodes and LINKS_TO edges in Neo4j
- [ ] Verify: ingest a real vault, query Neo4j browser to confirm graph structure

### Phase 3: Chunking & Embedding

- [ ] Implement `Chunker.chunk_note()` — heading-aware chunking with size limits
- [ ] Implement chunk merging logic (merge small chunks with predecessor)
- [ ] Implement `GraphStore.upsert_chunk()` in Neo4j — create Chunk nodes with HAS_CHUNK edge to parent Note
- [ ] Implement embedding batch pipeline — chunk all notes in a vault, embed in batches, store vectors
- [ ] Create Neo4j vector index on Chunk.embedding property
- [ ] Implement `GraphStore.find_similar_chunks()` — vector similarity query
- [ ] Integrate chunking + embedding into the `/ingest/vault` pipeline (parse → chunk → embed → store)
- [ ] Write tests for chunker: heading splits, paragraph splits, min/max size enforcement
- [ ] Write tests for embedding: verify dimensions, verify normalization
- [ ] Write integration test: ingest + chunk + embed → vector search returns relevant results
- [ ] Verify: after ingesting a vault, run a semantic query and confirm meaningful results

### Phase 4: Semantic Linking & Deduplication

- [ ] Implement `SemanticLinker.link_all()` — iterate chunks, KNN search, create SIMILAR_TO edges
- [ ] Implement same-note exclusion filter (don't link chunks from the same note)
- [ ] Implement `SemanticLinker.derive_note_relationships()` — aggregate SIMILAR_TO into RELATED_TO
- [ ] Implement `dedup.py` — title-based duplicate detection across vaults
- [ ] Implement embedding-based near-duplicate detection (high threshold, e.g., 0.92)
- [ ] Implement duplicate resolution strategy (keep longer/newer, merge references)
- [ ] Implement `POST /api/v1/link` endpoint
- [ ] Write tests for linker: verify SIMILAR_TO edges created with correct scores
- [ ] Write tests for note relationship derivation
- [ ] Write tests for dedup: exact title match, near-duplicate detection
- [ ] Verify: after linking, query cross-vault RELATED_TO edges in Neo4j, confirm they're meaningful

### Phase 5: Knowledge Export

- [ ] Implement `VaultExporter.export()` — iterate all notes, generate markdown files
- [ ] Implement `_build_references_section()` — format LINKS_TO and RELATED_TO as wikilinks
- [ ] Implement filename conflict resolution (append vault name for duplicates)
- [ ] Implement frontmatter generation (title, source_vault, garden_id)
- [ ] Implement content cleaning — strip old frontmatter, normalize wikilinks to new titles
- [ ] Implement wikilink rewriting — update `[[old target]]` to `[[new title]]` based on graph
- [ ] Implement `POST /api/v1/export` endpoint
- [ ] Write tests for reference section formatting
- [ ] Write tests for filename conflict resolution
- [ ] Write tests for wikilink rewriting
- [ ] Verify: export vault, open in Obsidian, confirm graph view shows both explicit and discovered links

### Phase 6: Search API & Refinement

- [ ] Implement `POST /api/v1/search` endpoint — embed query, vector search, return enriched results
- [ ] Implement `GET /api/v1/stats` endpoint — note count, edge count, vault count, chunk count
- [ ] Add structured logging throughout all services
- [ ] Add error handling and meaningful error responses for all endpoints
- [ ] Add progress reporting for long-running operations (ingestion, linking, export)
- [ ] Write integration test: full pipeline end-to-end (ingest → link → export → search)
- [ ] Final verification: process a real vault set, review exported vault in Obsidian
