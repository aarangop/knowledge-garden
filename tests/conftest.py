"""Shared pytest fixtures for the Knowledge Garden test suite.

Contract reference: specifications/01_foundation/contract.md, section 8.
"""
import os
from unittest.mock import AsyncMock

import pytest

from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore


@pytest.fixture
def mock_embedder():
    """Mock EmbeddingService that returns deterministic 768-dim vectors.

    Contract: section 8 — mock_embedder fixture.
    """
    embedder = AsyncMock(spec=EmbeddingService)
    embedder.dimension.return_value = 768
    embedder.embed.return_value = [[0.1] * 768]  # single deterministic vector
    return embedder


@pytest.fixture
def mock_graph_store():
    """Mock GraphStore for unit testing.

    Contract: section 8 — mock_graph_store fixture.
    """
    store = AsyncMock(spec=GraphStore)
    return store


def mock_together_response(num_embeddings: int = 1, dimension: int = 768) -> dict:
    """Generate a mock Together AI /embeddings response dict.

    Plain helper function (not a fixture) — import and call directly in tests.
    Contract: section 8 — mock_together_response helper.
    """
    return {
        "data": [
            {"embedding": [0.1] * dimension, "index": i}
            for i in range(num_embeddings)
        ],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "total_tokens": 10},
    }


@pytest.fixture
async def neo4j_store():
    """Real Neo4jGraphStore connected to the **test** Neo4j instance.

    Connection is read from environment variables, defaulting to the
    isolated test container declared in docker-compose.yml under the
    "test" profile (port 7688). This keeps the dev Neo4j instance on
    7687 untouched by the destructive teardown below.

    Env overrides:
        KG_TEST_NEO4J_URI       (default: bolt://localhost:7688)
        KG_TEST_NEO4J_USER      (default: neo4j)
        KG_TEST_NEO4J_PASSWORD  (default: knowledge-garden-test)
        KG_TEST_NEO4J_DATABASE  (default: neo4j)

    Setup: creates and initializes the store.
    Teardown: deletes all nodes and relationships, then closes the driver.

    Start the test instance with:
        docker compose --profile test up -d neo4j-test
    """
    from knowledge_garden.config import EmbeddingConfig, Neo4jConfig
    from knowledge_garden.services.neo4j_store import Neo4jGraphStore

    neo4j_config = Neo4jConfig(
        uri=os.environ.get("KG_TEST_NEO4J_URI", "bolt://localhost:7688"),
        user=os.environ.get("KG_TEST_NEO4J_USER", "neo4j"),
        password=os.environ.get("KG_TEST_NEO4J_PASSWORD", "knowledge-garden-test"),
        database=os.environ.get("KG_TEST_NEO4J_DATABASE", "neo4j"),
    )
    embedding_config = EmbeddingConfig()

    store = Neo4jGraphStore(neo4j_config, embedding_config)
    await store.initialize()

    yield store

    # Teardown: wipe all data, then close the driver.
    # Guard against tests that explicitly call close() themselves (driver already closed).
    from neo4j.exceptions import DriverError
    try:
        async with store._driver.session(database=store._database) as session:
            await session.run("MATCH (n) DETACH DELETE n")
        await store.close()
    except DriverError:
        pass
