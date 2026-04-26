"""Tests for FastAPI application — contract: specifications/01_foundation/contract.md, section 7
and specifications/02_ingestion/contract.md, section 3.6."""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Contract section 7.2 — FastAPI application tests."""

    @pytest.mark.unit
    def test_health_endpoint(self):
        """Contract: GET /api/v1/health returns HTTP 200 when services are mocked."""
        # Ensure a fresh import each time so patching takes effect
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_config = MagicMock()
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_embedder_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app) as client:
                response = client.get("/api/v1/health")

        assert response.status_code == 200

    @pytest.mark.unit
    def test_health_response_schema(self):
        """Contract: GET /api/v1/health response body contains keys status, neo4j, together_ai."""
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_config = MagicMock()
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_embedder_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app) as client:
                response = client.get("/api/v1/health")

        body = response.json()
        assert "status" in body
        assert "neo4j" in body
        assert "together_ai" in body

    @pytest.mark.unit
    def test_app_startup_initializes_services(self):
        """Contract: After app startup, app.state.graph_store and app.state.embedder are set."""
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_config = MagicMock()
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_embedder_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app):
                assert hasattr(app.state, "graph_store")
                assert hasattr(app.state, "embedder")


class TestLifespanProviderDispatch:
    """Contract section 3.6 — lifespan selects embedder based on config.embedding.provider."""

    @pytest.mark.unit
    def test_lifespan_selects_together_embedder(self):
        """Contract: provider='together' → TogetherAIEmbedder is instantiated, no ValueError raised.
        """
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_together_cls, \
             patch("knowledge_garden.main.HuggingFaceEmbedder") as mock_hf_cls:

            mock_config = MagicMock()
            mock_config.embedding.provider = "together"
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_together_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app):
                pass

            assert mock_together_cls.called
            assert not mock_hf_cls.called

    @pytest.mark.unit
    def test_lifespan_selects_hf_embedder(self):
        """Contract: provider='huggingface' with valid hugging_face config → HuggingFaceEmbedder
        is instantiated.
        """
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_together_cls, \
             patch("knowledge_garden.main.HuggingFaceEmbedder") as mock_hf_cls:

            mock_hf_config = MagicMock()
            mock_hf_config.api_key = "test-token"
            mock_hf_config.base_url = "https://api-inference.huggingface.co"

            mock_config = MagicMock()
            mock_config.embedding.provider = "huggingface"
            mock_config.hugging_face = mock_hf_config
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_hf_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app):
                pass

            assert mock_hf_cls.called
            assert not mock_together_cls.called

    @pytest.mark.unit
    def test_lifespan_unknown_provider_raises(self):
        """Contract: provider='unknown' → ValueError raised at startup containing
        'Unknown embedding provider'.
        """
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.Config") as mock_config_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder"), \
             patch("knowledge_garden.main.HuggingFaceEmbedder"):

            mock_config = MagicMock()
            mock_config.embedding.provider = "unknown"
            mock_config_cls.from_yaml.return_value = mock_config

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            from knowledge_garden.main import app
            with pytest.raises(Exception) as exc_info, TestClient(app):
                pass

        assert "Unknown embedding provider" in str(exc_info.value)
