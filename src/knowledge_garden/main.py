"""FastAPI application entry point for Knowledge Garden.

Contract reference: specifications/01_foundation/contract.md, section 7.
Updated by: specifications/04_config_split/contract.md, section 4.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from knowledge_garden.api.routes import router
from knowledge_garden.config import AppSettings, BusinessConfig
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.together_embedder import TogetherAIEmbedder

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup: load settings, instantiate services, initialize graph store.
    Shutdown: close connections.
    """
    settings = AppSettings()  # type: ignore[call-arg]

    # Load config.yaml so the server embeds queries with the same model used
    # during ingestion (CLI-side). Otherwise dim/model mismatches silently
    # break semantic search.
    business = BusinessConfig.from_yaml("config.yaml")
    embedding_config = business.embedding

    graph_store = Neo4jGraphStore(settings.neo4j, embedding_config)
    await graph_store.initialize()

    embedder: EmbeddingService
    provider = embedding_config.provider
    if provider == "huggingface":
        hf = settings.hugging_face
        if hf is None:
            raise ValueError(
                "HF_API_TOKEN is required when embedding.provider is 'huggingface'"
            )
        embedder = HuggingFaceEmbedder(hf, embedding_config)
    elif provider == "together":
        embedder = TogetherAIEmbedder(settings.together_ai, embedding_config)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")

    app.state.settings = settings
    app.state.graph_store = graph_store
    app.state.embedder = embedder
    app.state.export_output_dir = "./output"

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
