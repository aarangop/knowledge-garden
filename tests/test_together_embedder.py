"""Tests for TogetherAIEmbedder — contract: specifications/01_foundation/contract.md, section 6."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import together

from knowledge_garden.config import EmbeddingConfig, TogetherAIConfig
from knowledge_garden.services.together_embedder import TogetherAIEmbedder


def make_embedder(batch_size: int = 64, dimension: int = 768) -> TogetherAIEmbedder:
    together_config = TogetherAIConfig(api_key="test-key")
    embedding_config = EmbeddingConfig(batch_size=batch_size, dimension=dimension)
    return TogetherAIEmbedder(together_config, embedding_config)


def make_sdk_response(num_embeddings: int, dimension: int) -> MagicMock:
    """Build a mock Together SDK embeddings response."""
    items = []
    for _ in range(num_embeddings):
        item = MagicMock()
        item.embedding = [0.1] * dimension
        items.append(item)
    resp = MagicMock()
    resp.data = items
    return resp


class TestTogetherAIEmbedder:
    """Contract section 6.2 — Together AI Embedder tests."""

    @pytest.mark.unit
    async def test_embed_single_text(self):
        """Contract: embed(["hello"]) returns exactly 1 vector of the configured dimension."""
        embedder = make_embedder(dimension=768)
        with patch.object(
            embedder._client.embeddings, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = make_sdk_response(1, 768)
            result = await embedder.embed(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.unit
    async def test_embed_batch(self):
        """Contract: embed(["a", "b", "c"]) returns exactly 3 vectors."""
        embedder = make_embedder(dimension=768)
        with patch.object(
            embedder._client.embeddings, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = make_sdk_response(3, 768)
            result = await embedder.embed(["a", "b", "c"])

        assert len(result) == 3
        for vector in result:
            assert len(vector) == 768

    @pytest.mark.unit
    async def test_embed_batching_splits_large_input(self):
        """Contract: 100 texts with batch_size=64 triggers exactly 2 SDK calls."""
        embedder = make_embedder(batch_size=64, dimension=768)

        def side_effect(**kwargs):
            n = len(kwargs.get("input", []))
            return make_sdk_response(n, 768)

        with patch.object(
            embedder._client.embeddings, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = side_effect
            result = await embedder.embed(["text"] * 100)

        assert mock_create.call_count == 2
        assert len(result) == 100

    @pytest.mark.unit
    async def test_embed_empty_list(self):
        """Edge case: embed([]) returns an empty list without making any SDK calls."""
        embedder = make_embedder()
        with patch.object(
            embedder._client.embeddings, "create", new_callable=AsyncMock
        ) as mock_create:
            result = await embedder.embed([])

        assert result == []
        mock_create.assert_not_called()

    @pytest.mark.unit
    async def test_embed_api_error_propagates(self):
        """Edge case: when the SDK raises APIError, it propagates to the caller."""
        embedder = make_embedder()
        with patch.object(
            embedder._client.embeddings, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = together.APIError(
                message="Internal Server Error",
                request=MagicMock(),
                body=None,
            )
            with pytest.raises(together.APIError):
                await embedder.embed(["hello"])

    @pytest.mark.unit
    def test_dimension_returns_configured(self):
        """Contract: dimension() returns the value from EmbeddingConfig.dimension."""
        embedder = make_embedder(dimension=768)
        assert embedder.dimension() == 768

    @pytest.mark.unit
    async def test_close_closes_client(self):
        """Contract: close() calls close() on the underlying SDK client."""
        embedder = make_embedder()
        with patch.object(embedder._client, "close", new_callable=AsyncMock) as mock_close:
            await embedder.close()
        mock_close.assert_called_once()

    @pytest.mark.integration
    async def test_embed_real_api(self):
        """Integration: real Together AI call returns vectors of the correct dimension.

        Skipped automatically when TOGETHER_API_KEY is not set in the environment.
        """
        api_key = os.environ.get("TOGETHER_API_KEY")
        if not api_key:
            pytest.skip("TOGETHER_API_KEY not set — skipping real API test")

        together_config = TogetherAIConfig(api_key=api_key)
        embedding_config = EmbeddingConfig(dimension=768, batch_size=64)
        embedder = TogetherAIEmbedder(together_config, embedding_config)

        try:
            result = await embedder.embed(["Knowledge garden integration test."])
        finally:
            await embedder.close()

        assert len(result) == 1
        assert len(result[0]) == embedding_config.dimension
