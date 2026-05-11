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
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_settings = MagicMock()
            mock_settings.hugging_face = None
            mock_settings_cls.return_value = mock_settings

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

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_settings = MagicMock()
            mock_settings.hugging_face = None
            mock_settings_cls.return_value = mock_settings

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

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_embedder_cls:

            mock_settings = MagicMock()
            mock_settings.hugging_face = None
            mock_settings_cls.return_value = mock_settings

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_emb = AsyncMock()
            mock_embedder_cls.return_value = mock_emb

            from knowledge_garden.main import app
            with TestClient(app):
                assert hasattr(app.state, "graph_store")
                assert hasattr(app.state, "embedder")


class TestLifespanProviderDispatch:
    """Contract section 3.6 — lifespan selects embedder based on AppSettings.hugging_face."""

    @pytest.mark.unit
    def test_lifespan_selects_together_embedder(self):
        """Contract: hugging_face is None → TogetherAIEmbedder is instantiated."""
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_together_cls, \
             patch("knowledge_garden.main.HuggingFaceEmbedder") as mock_hf_cls:

            mock_settings = MagicMock()
            mock_settings.hugging_face = None
            mock_settings_cls.return_value = mock_settings

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
        """Contract: hugging_face is not None → HuggingFaceEmbedder is instantiated."""
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_together_cls, \
             patch("knowledge_garden.main.HuggingFaceEmbedder") as mock_hf_cls:

            mock_hf_config = MagicMock()
            mock_hf_config.api_key = "test-token"

            mock_settings = MagicMock()
            mock_settings.hugging_face = mock_hf_config
            mock_settings_cls.return_value = mock_settings

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
    def test_lifespan_together_not_used_when_hf_present(self):
        """Contract: hugging_face present → TogetherAIEmbedder is never instantiated."""
        sys.modules.pop("knowledge_garden.main", None)

        with patch("knowledge_garden.main.AppSettings") as mock_settings_cls, \
             patch("knowledge_garden.main.Neo4jGraphStore") as mock_store_cls, \
             patch("knowledge_garden.main.TogetherAIEmbedder") as mock_together_cls, \
             patch("knowledge_garden.main.HuggingFaceEmbedder") as mock_hf_cls:

            mock_settings = MagicMock()
            mock_settings.hugging_face = MagicMock()
            mock_settings_cls.return_value = mock_settings

            mock_store = AsyncMock()
            mock_store_cls.return_value = mock_store

            mock_hf_cls.return_value = AsyncMock()

            from knowledge_garden.main import app
            with TestClient(app):
                pass

            assert not mock_together_cls.called
