"""Together AI implementation of EmbeddingService.

Contract reference: specifications/01_foundation/contract.md, section 6.
"""
import httpx

from knowledge_garden.config import EmbeddingConfig, TogetherAIConfig
from knowledge_garden.services.embedder import EmbeddingService


class TogetherAIEmbedder(EmbeddingService):
    """Embedding via Together AI API."""

    def __init__(
        self, together_config: TogetherAIConfig, embedding_config: EmbeddingConfig
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=together_config.base_url,
            headers={"Authorization": f"Bearer {together_config.api_key}"},
            timeout=60.0,
        )
        self._model = embedding_config.model
        self._dimension = embedding_config.dimension
        self._batch_size = embedding_config.batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed via Together AI /embeddings endpoint. Batches internally."""
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = await self._client.post(
                "/embeddings",
                json={"model": self._model, "input": batch},
            )
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend([item["embedding"] for item in data["data"]])
        return all_embeddings

    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        return self._dimension

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        await self._client.aclose()
