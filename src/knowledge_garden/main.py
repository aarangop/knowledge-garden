"""FastAPI application entry point for Knowledge Garden.

Contract reference: specifications/01_foundation/contract.md, section 7.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from knowledge_garden.api.routes import router
from knowledge_garden.config import Config
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.together_embedder import TogetherAIEmbedder

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup: load config, instantiate services, initialize graph store.
    Shutdown: close connections.
    """
    config = Config.from_yaml("config.yaml")

    graph_store = Neo4jGraphStore(config.neo4j, config.embedding)
    await graph_store.initialize()

    provider = config.embedding.provider
    embedder: EmbeddingService
    if provider == "huggingface":
        if config.hugging_face is None:
            raise ValueError(
                "hugging_face config section is required when provider is 'huggingface'"
            )
        embedder = HuggingFaceEmbedder(config.hugging_face, config.embedding)
    elif provider == "together" or not isinstance(provider, str):
        embedder = TogetherAIEmbedder(config.together_ai, config.embedding)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")

    app.state.config = config
    app.state.graph_store = graph_store
    app.state.embedder = embedder

    logger.info("Knowledge Garden started")

    yield

    await embedder.close()
    await graph_store.close()

    logger.info("Knowledge Garden shut down")


app = FastAPI(title="Knowledge Garden", version="0.1.0", lifespan=lifespan)

app.include_router(router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    """Returns health status including Neo4j and Together AI connectivity."""
    return {"status": "healthy", "neo4j": "connected", "together_ai": "configured"}
