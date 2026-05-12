"""Tests for HuggingFaceEmbedder — contract: specifications/05_hf_sdk_embedder/contract.md"""
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder


@pytest.fixture
def hf_config() -> HuggingFaceConfig:
    return HuggingFaceConfig(api_key="test-token")


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        model="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
        batch_size=64,
    )


@pytest.fixture
def embedder(hf_config, embedding_config) -> HuggingFaceEmbedder:
    return HuggingFaceEmbedder(hf_config, embedding_config)


def _patch_fe(embedder):
    return patch.object(
        embedder._client, "feature_extraction", new_callable=AsyncMock
    )


class TestHuggingFaceEmbedder:
    """Contract section 6.1 — HuggingFaceEmbedder unit tests (SDK-based)."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_single_text(self, embedder):
        mock_ndarray = np.array([[0.1] * 384])
        with _patch_fe(embedder) as mock_fe:
            mock_fe.return_value = mock_ndarray
            result = await embedder.embed(["hello"])

        assert result == [[0.1] * 384]
        mock_fe.assert_called_once()
        assert mock_fe.call_args[0][0] == ["hello"]
        assert mock_fe.call_args.kwargs["model"] == (
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_batch(self, embedder):
        mock_ndarray = np.array([[0.1] * 384, [0.2] * 384, [0.3] * 384])
        with _patch_fe(embedder) as mock_fe:
            mock_fe.return_value = mock_ndarray
            result = await embedder.embed(["a", "b", "c"])

        assert len(result) == 3
        assert len(result[0]) == 384
        assert result[0] == [0.1] * 384
        mock_fe.assert_called_once()
        assert mock_fe.call_args[0][0] == ["a", "b", "c"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_batching_splits_large_input(self, hf_config):
        small_batch_config = EmbeddingConfig(
            model="sentence-transformers/all-MiniLM-L6-v2",
            dimension=384,
            batch_size=64,
        )
        embedder = HuggingFaceEmbedder(hf_config, small_batch_config)

        first_batch = np.array([[0.1] * 384] * 64)
        second_batch = np.array([[0.1] * 384] * 36)

        with _patch_fe(embedder) as mock_fe:
            mock_fe.side_effect = [first_batch, second_batch]
            result = await embedder.embed(["x"] * 100)

        assert mock_fe.call_count == 2
        assert mock_fe.call_args_list[0][0][0] == ["x"] * 64
        assert mock_fe.call_args_list[1][0][0] == ["x"] * 36
        assert len(result) == 100

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_empty_list(self, embedder):
        with _patch_fe(embedder) as mock_fe:
            result = await embedder.embed([])

        assert result == []
        mock_fe.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_api_error_propagates(self, embedder):
        with _patch_fe(embedder) as mock_fe:
            mock_fe.side_effect = RuntimeError("API error")
            with pytest.raises(RuntimeError, match="API error"):
                await embedder.embed(["text"])

    @pytest.mark.unit
    def test_hf_dimension_returns_configured(self, embedder, embedding_config):
        assert embedder.dimension() == embedding_config.dimension

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_close_closes_client(self, embedder):
        with patch.object(embedder._client, "close", new_callable=AsyncMock) as mock_close:
            await embedder.close()
        mock_close.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_hf_embed_single_text_1d_reshaped(self, hf_config):
        config = EmbeddingConfig(
            model="test-model", dimension=384, batch_size=64
        )
        embedder = HuggingFaceEmbedder(hf_config, config)
        mock_ndarray = np.array([0.1] * 384)
        with _patch_fe(embedder) as mock_fe:
            mock_fe.return_value = mock_ndarray
            result = await embedder.embed(["hello"])

        assert result == [[0.1] * 384]

    @pytest.mark.unit
    def test_hf_client_pins_hf_inference_provider(self, hf_config, embedding_config):
        # Pinning provider="hf-inference" bypasses the SDK's per-model provider
        # lookup, which raises StopIteration for models with no provider mapping
        # (e.g. intfloat/multilingual-e5-large-instruct on huggingface_hub 1.12+).
        with patch(
            "knowledge_garden.services.hf_embedder.AsyncInferenceClient"
        ) as mock_client:
            HuggingFaceEmbedder(hf_config, embedding_config)

        mock_client.assert_called_once()
        assert mock_client.call_args.kwargs.get("provider") == "hf-inference"
