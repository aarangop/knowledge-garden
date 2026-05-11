"""Together AI implementation of EmbeddingService.

Contract reference: specifications/01_foundation/contract.md, section 6.
"""
from together import AsyncTogether

from knowledge_garden.config import EmbeddingConfig, TogetherAIConfig
from knowledge_garden.services.embedder import EmbeddingService


class TogetherAIEmbedder(EmbeddingService):
    """Embedding via Together AI SDK."""

    def __init__(
        self, together_config: TogetherAIConfig, embedding_config: EmbeddingConfig
    ) -> None:
        self._client = AsyncTogether(api_key=together_config.api_key)
        self._model = embedding_config.model
        self._dimension = embedding_config.dimension
        self._batch_size = embedding_config.batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via Together AI SDK. Batches internally."""
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = await self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])
        return all_embeddings

    def dimension(self) -> int:
        return self._dimension

    async def close(self) -> None:
        await self._client.close()
