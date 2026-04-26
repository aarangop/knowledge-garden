"""Tests for TogetherAIEmbedder — contract: specifications/01_foundation/contract.md, section 6."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from knowledge_garden.config import EmbeddingConfig, TogetherAIConfig
from knowledge_garden.services.together_embedder import TogetherAIEmbedder  # does NOT exist yet
from tests.conftest import mock_together_response


def make_embedder(batch_size: int = 64, dimension: int = 768) -> TogetherAIEmbedder:
    """Helper to construct a TogetherAIEmbedder with test configuration."""
    together_config = TogetherAIConfig(api_key="test-key")
    embedding_config = EmbeddingConfig(batch_size=batch_size, dimension=dimension)
    return TogetherAIEmbedder(together_config, embedding_config)


class TestTogetherAIEmbedder:
    """Contract section 6.2 — Together AI Embedder tests."""

    @pytest.mark.unit
    async def test_embed_single_text(self):
        """Contract: embed(["hello"]) returns exactly 1 vector of the configured dimension."""
        embedder = make_embedder(dimension=768)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_together_response(num_embeddings=1, dimension=768)

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await embedder.embed(["hello"])

        assert len(result) == 1
        assert len(result[0]) == 768

    @pytest.mark.unit
    async def test_embed_batch(self):
        """Contract: embed(["a", "b", "c"]) returns exactly 3 vectors."""
        embedder = make_embedder(dimension=768)
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_together_response(num_embeddings=3, dimension=768)

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await embedder.embed(["a", "b", "c"])

        assert len(result) == 3
        for vector in result:
            assert len(vector) == 768

    @pytest.mark.unit
    async def test_embed_batching_splits_large_input(self):
        """Contract: 100 texts with batch_size=64 triggers exactly 2 HTTP POST calls."""
        embedder = make_embedder(batch_size=64, dimension=768)

        # First batch: 64 texts, second batch: 36 texts
        def side_effect(*args, **kwargs):
            payload = kwargs.get("json", {})
            n = len(payload.get("input", []))
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = mock_together_response(num_embeddings=n, dimension=768)
            return resp

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = side_effect
            result = await embedder.embed(["text"] * 100)

        assert mock_post.call_count == 2
        assert len(result) == 100

    @pytest.mark.unit
    async def test_embed_empty_list(self):
        """Edge case: embed([]) returns an empty list without making any HTTP calls."""
        embedder = make_embedder()

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            result = await embedder.embed([])

        assert result == []
        mock_post.assert_not_called()

    @pytest.mark.unit
    async def test_embed_api_error_propagates(self):
        """Edge case: when httpx raises HTTPStatusError (500), it propagates to the caller."""
        embedder = make_embedder()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(),
        )

        with patch.object(embedder._client, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                await embedder.embed(["hello"])

    @pytest.mark.unit
    def test_dimension_returns_configured(self):
        """Contract: dimension() returns the value from EmbeddingConfig.dimension."""
        embedder = make_embedder(dimension=768)
        assert embedder.dimension() == 768

    @pytest.mark.unit
    async def test_close_closes_client(self):
        """Contract: after close(), the underlying httpx.AsyncClient is closed."""
        embedder = make_embedder()
        await embedder.close()
        assert embedder._client.is_closed

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
