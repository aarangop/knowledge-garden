"""Integration tests for HuggingFaceEmbedder — real API calls.

Contract: specifications/06_hf_embedder_integration/contract.md, section 2.
Skipped automatically when HF_API_TOKEN is not set.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder

HF_API_TOKEN = os.environ.get("HF_API_TOKEN")
SKIP_REASON = "HF_API_TOKEN not set — skipping real API test"

DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct"
DEFAULT_DIMENSION = 1024
DEFAULT_BATCH_SIZE = 8


@pytest.fixture
def hf_config() -> HuggingFaceConfig:
    return HuggingFaceConfig(api_key=HF_API_TOKEN)


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        model=DEFAULT_MODEL,
        dimension=DEFAULT_DIMENSION,
        batch_size=DEFAULT_BATCH_SIZE,
    )


@pytest.fixture
def embedder(hf_config, embedding_config) -> HuggingFaceEmbedder:
    return HuggingFaceEmbedder(hf_config, embedding_config)


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)
async def test_hf_embed_single_text_real(embedder, embedding_config):
    result = await embedder.embed(["Knowledge garden integration test."])
    await embedder.close()

    assert len(result) == 1
    assert len(result[0]) == embedding_config.dimension


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)
async def test_hf_embed_batch_produces_independent_vectors(embedder, embedding_config):
    result = await embedder.embed(["cat", "dog", "automobile"])
    await embedder.close()

    assert len(result) == 3
    for vec in result:
        assert len(vec) == embedding_config.dimension

    cat_vec = np.array(result[0])
    auto_vec = np.array(result[2])
    cos_sim = float(
        np.dot(cat_vec, auto_vec)
        / (np.linalg.norm(cat_vec) * np.linalg.norm(auto_vec))
    )
    assert cos_sim < 0.95, (
        f"cat and automobile too similar (cos={cos_sim:.3f}) — inputs may be concatenated"
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)
async def test_hf_embed_batch_vs_individual_match(hf_config, embedding_config):
    text = "hello world"

    batch_embedder = HuggingFaceEmbedder(hf_config, embedding_config)
    batch_result = await batch_embedder.embed([text])
    await batch_embedder.close()

    individual_embedder = HuggingFaceEmbedder(hf_config, embedding_config)
    individual_result = await individual_embedder.embed([text])
    await individual_embedder.close()

    batch_vec = np.array(batch_result[0])
    ind_vec = np.array(individual_result[0])
    cos_sim = float(
        np.dot(batch_vec, ind_vec)
        / (np.linalg.norm(batch_vec) * np.linalg.norm(ind_vec))
    )
    assert cos_sim >= 0.999, (
        f"Batch and individual vectors differ (cos={cos_sim:.6f})"
    )


@pytest.mark.integration
@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)
def test_hf_embed_dimension_matches_config(embedder, embedding_config):
    assert embedder.dimension() == embedding_config.dimension


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(not HF_API_TOKEN, reason=SKIP_REASON)
async def test_hf_embed_empty_list_real(embedder):
    result = await embedder.embed([])
    assert result == []
