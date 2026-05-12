"""HuggingFace Inference API implementation of EmbeddingService.

Contract reference: specifications/05_hf_sdk_embedder/contract.md, section 4.
"""

from __future__ import annotations

import numpy as np
from huggingface_hub import AsyncInferenceClient

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.embedder import EmbeddingService


class HuggingFaceEmbedder(EmbeddingService):
    """Embedding via HuggingFace Inference API using the SDK client.

    Uses AsyncInferenceClient.feature_extraction() with batch inputs.
    The HF Inference API accepts string[] as inputs for feature-extraction,
    returning one embedding vector per input string.
    """

    def __init__(self, hf_config: HuggingFaceConfig, embedding_config: EmbeddingConfig) -> None:
        self._client = AsyncInferenceClient(
            token=hf_config.api_key,
            provider="hf-inference",
            timeout=120.0,
        )
        self._embedding_config = embedding_config

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via feature_extraction. Batches internally.

        Returns [] immediately for empty input without making any API calls.
        Splits texts into batch_size chunks and calls feature_extraction
        once per chunk, passing the list of strings. Converts each
        np.ndarray row to list[float].

        Parameters
        ----------
        texts:
            List of strings to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in input order.

        Raises
        ------
        Exception
            Any exception raised by AsyncInferenceClient.feature_extraction
            (e.g., huggingface_hub.errors.HttpError) propagates to the caller.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        batch_size = self._embedding_config.batch_size
        model = self._embedding_config.model

        for i in range(0, len(texts), batch_size):
            chunk = texts[i : i + batch_size]
            # feature_extraction accepts list[str] at runtime but SDK types show str only.
            # See https://github.com/huggingface/huggingface_hub/issues/2824
            ndarray: np.ndarray = await self._client.feature_extraction(chunk, model=model)  # type: ignore[arg-type]
            if ndarray.ndim == 1:
                ndarray = ndarray.reshape(1, -1)
            all_embeddings.extend(ndarray.tolist())

        return all_embeddings

    def dimension(self) -> int:
        return self._embedding_config.dimension

    async def close(self) -> None:
        await self._client.close()  # type: ignore[no-untyped-call]
