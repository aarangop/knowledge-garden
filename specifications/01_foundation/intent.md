# Intent: Foundation

Set up the project infrastructure so that all subsequent phases have a working base to build on. This means a running FastAPI application, a live connection to Neo4j, a working embedding pipeline via Together AI, and the core data models that every other component will depend on.

By the end of this phase, the system starts up, confirms it can reach Neo4j and Together AI, and the graph database has the correct indexes and constraints in place. No vaults are processed yet — this is purely the skeleton.

This phase also establishes the abstract interfaces (`EmbeddingService`, `GraphStore`) that allow swapping backends without touching business logic. The concrete implementations (Neo4j, Together AI) are wired up via configuration and dependency injection through FastAPI's lifespan.

**Expected outcome:** Run `uv run uvicorn knowledge_garden.main:app` and hit `/api/v1/health` to get a 200 confirming Neo4j connectivity and Together AI reachability. The graph database has `Note` and `Chunk` constraints and a vector index ready for embeddings.
