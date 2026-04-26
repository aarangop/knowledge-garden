"""HuggingFace Inference API implementation of EmbeddingService.

Contract reference: specifications/02_ingestion/contract.md, section 3.5.
"""
import httpx

from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.embedder import EmbeddingService


class HuggingFaceEmbedder(EmbeddingService):
    """Embedding via HuggingFace Inference API."""

    def __init__(self, hf_config: HuggingFaceConfig, embedding_config: EmbeddingConfig) -> None:
        self._hf_config = hf_config
        self._embedding_config = embedding_config
        self._client = httpx.AsyncClient(
            base_url=hf_config.base_url,
            headers={"Authorization": f"Bearer {hf_config.api_key}"},
            timeout=30.0,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via POST /models/{model_id}. Batches internally."""
        if not texts:
            return []
        all_embeddings: list[list[float]] = []
        model_id = self._embedding_config.model
        batch_size = self._embedding_config.batch_size
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = await self._client.post(
                f"/models/{model_id}",
                json={"inputs": batch},
            )
            response.raise_for_status()
            data: list[list[float]] = response.json()
            all_embeddings.extend(data)
        return all_embeddings

    def dimension(self) -> int:
        return self._embedding_config.dimension

    async def close(self) -> None:
        await self._client.aclose()
