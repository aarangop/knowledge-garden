"""Tests for HuggingFaceEmbedder — contract: specifications/02_ingestion/contract.md, section 3.5"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder


@pytest.fixture
def hf_config() -> HuggingFaceConfig:
    """HuggingFaceConfig with a test token."""
    return HuggingFaceConfig(api_key="test-token")


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    """EmbeddingConfig pointing at a small sentence-transformer model."""
    return EmbeddingConfig(
        model="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
        batch_size=64,
    )


@pytest.fixture
def embedder(hf_config, embedding_config) -> HuggingFaceEmbedder:
    """Constructed HuggingFaceEmbedder ready for patching."""
    return HuggingFaceEmbedder(hf_config, embedding_config)


class TestHuggingFaceEmbedder:
    """Contract section 3.5 — HuggingFaceEmbedder unit tests."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_single_text(self, embedder):
        """Contract: embed(['hello']) with mock returning [[0.1]*384] → 1 vector of 384 floats."""
        mock_response = MagicMock()
        mock_response.json.return_value = [[0.1] * 384]
        mock_response.raise_for_status = MagicMock()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await embedder.embed(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 384

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_batch(self, embedder):
        """Contract: embed(['a', 'b', 'c']) with mock returning 3 vectors → list of length 3."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            [0.1] * 384,
            [0.2] * 384,
            [0.3] * 384,
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await embedder.embed(["a", "b", "c"])

        assert len(result) == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_batching_splits_large_input(self, hf_config):
        """Contract: 100 texts with batch_size=64 → exactly 2 HTTP POST calls."""
        small_batch_config = EmbeddingConfig(
            model="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
            batch_size=64,
        )
        embedder = HuggingFaceEmbedder(hf_config, small_batch_config)

        # First call returns 64 vectors, second returns 36
        first_response = MagicMock()
        first_response.json.return_value = [[0.1] * 384] * 64
        first_response.raise_for_status = MagicMock()

        second_response = MagicMock()
        second_response.json.return_value = [[0.1] * 384] * 36
        second_response.raise_for_status = MagicMock()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [first_response, second_response]
            result = await embedder.embed(["x"] * 100)

        assert mock_post.call_count == 2
        assert len(result) == 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_empty_list(self, embedder):
        """Contract: embed([]) returns [] immediately with no HTTP call made."""
        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            result = await embedder.embed([])

        assert result == []
        mock_post.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_api_error_propagates(self, embedder):
        """Contract: mock returning HTTP 503 → embed raises httpx.HTTPStatusError."""
        request = httpx.Request("POST", "https://api-inference.huggingface.co/models/test")
        error_response = httpx.Response(503, request=request)

        def raise_status():
            raise httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=request,
                response=error_response,
            )

        mock_response = MagicMock()
        mock_response.raise_for_status = raise_status

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                await embedder.embed(["text"])

    @pytest.mark.unit
    def test_hf_dimension_returns_configured(self, embedder, embedding_config):
        """Contract: dimension() returns the value from EmbeddingConfig.dimension (384)."""
        assert embedder.dimension() == embedding_config.dimension

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_close_closes_client(self, embedder):
        """Contract: after await embedder.close(), embedder._client.is_closed is True."""
        await embedder.close()
        assert embedder._client.is_closed is True
