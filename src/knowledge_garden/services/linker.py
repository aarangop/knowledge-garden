from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge_garden.services.graph_store import GraphStore

logger = logging.getLogger(__name__)


class LinkPhase(StrEnum):
    SIMILAR = "similar"
    RELATED = "related"


ProgressCallback = Callable[[LinkPhase, int, int, str], None]


@dataclass
class LinkResult:
    chunks_processed: int
    similarity_edges_created: int
    note_relationships_derived: int
    duration_seconds: float


class SemanticLinker:
    def __init__(
        self,
        graph_store: GraphStore,
        threshold: float = 0.7,
        max_neighbors: int = 20,
        batch_size: int = 100,
    ) -> None:
        self._graph_store = graph_store
        self._threshold = threshold
        self._max_neighbors = max_neighbors
        self._batch_size = batch_size

    async def link_all(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> LinkResult:
        start = time.monotonic()

        chunks = await self._graph_store.get_all_chunks()
        total = len(chunks)
        edges_created = 0

        for i, chunk in enumerate(chunks, start=1):
            try:
                matches = await self._graph_store.find_similar_chunks(
                    embedding=chunk.embedding,  # type: ignore[arg-type]
                    limit=self._max_neighbors,
                    threshold=self._threshold,
                )
            except Exception:
                logger.warning(
                    "find_similar_chunks failed for chunk %s, skipping",
                    chunk.id,
                    exc_info=True,
                )
                matches = []

            for match_chunk, score in matches:
                if match_chunk.note_id == chunk.note_id:
                    continue
                await self._graph_store.create_similarity(chunk.id, match_chunk.id, score)
                edges_created += 1

            if progress_callback is not None:
                progress_callback(LinkPhase.SIMILAR, i, total, f"{edges_created} edges")

        related_count = await self.derive_note_relationships(progress_callback=progress_callback)

        return LinkResult(
            chunks_processed=total,
            similarity_edges_created=edges_created,
            note_relationships_derived=related_count,
            duration_seconds=time.monotonic() - start,
        )

    async def derive_note_relationships(
        self,
        progress_callback: ProgressCallback | None = None,
    ) -> int:
        count = await self._graph_store.derive_related_to(threshold=self._threshold)
        if progress_callback is not None:
            progress_callback(LinkPhase.RELATED, 1, 1, f"{count} edges")
        return count
