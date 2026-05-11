from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from knowledge_garden.config import VaultConfig
from knowledge_garden.models.note import Chunk, Note
from knowledge_garden.services.chunker import NoteChunker
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.parser import MarkdownParser

logger = logging.getLogger(__name__)


class IngestPhase(StrEnum):
    CHUNKING = "chunking"
    DEDUP = "dedup"
    UPSERT = "upsert"


ProgressCallback = Callable[[IngestPhase, int, int, str], None]


@dataclass
class IngestResult:
    notes_parsed: int
    chunks_created: int
    chunks_skipped: int
    duration_seconds: float


class IngestPipeline:
    def __init__(
        self,
        parser: MarkdownParser,
        chunker: NoteChunker,
        embedder: EmbeddingService,
        graph_store: GraphStore,
        embed_batch_size: int = 32,
        dedup_threshold: float = 0.95,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._graph_store = graph_store
        self._embed_batch_size = embed_batch_size
        self._dedup_threshold = dedup_threshold

    async def run(
        self,
        vault_config: VaultConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestResult:
        start = time.monotonic()

        notes = self._parser.parse_vault(vault_config)
        total_notes = len(notes)

        all_chunks: list[Chunk] = []
        for i, note in enumerate(notes, start=1):
            if progress_callback is not None:
                progress_callback(
                    IngestPhase.CHUNKING, i, total_notes, note.title
                )
            all_chunks.extend(self._chunker.chunk_note(note))

        upserted_note_ids: set[UUID] = set()
        chunks_created = 0
        chunks_skipped = 0

        if all_chunks:
            total_chunks = len(all_chunks)
            texts = [chunk.content for chunk in all_chunks]
            num_batches = (
                total_chunks + self._embed_batch_size - 1
            ) // self._embed_batch_size

            for batch_idx in range(num_batches):
                start_idx = batch_idx * self._embed_batch_size
                end_idx = min(
                    start_idx + self._embed_batch_size, total_chunks
                )
                batch_texts = texts[start_idx:end_idx]
                batch_chunks = all_chunks[start_idx:end_idx]

                batch_vectors = await self._embedder.embed(batch_texts)
                for chunk, vector in zip(
                    batch_chunks, batch_vectors, strict=True
                ):
                    chunk.embedding = vector

                new_chunks: list[Chunk] = []
                for chunk in batch_chunks:
                    is_dup = False
                    try:
                        matches = (
                            await self._graph_store.find_similar_chunks(
                                embedding=chunk.embedding,  # type: ignore[arg-type]
                                limit=1,
                                threshold=self._dedup_threshold,
                            )
                        )
                        if matches:
                            is_dup = True
                    except Exception:
                        logger.warning(
                            "find_similar_chunks failed, treating as novel",
                            exc_info=True,
                        )
                    if is_dup:
                        chunks_skipped += 1
                    else:
                        new_chunks.append(chunk)

                dedup_checked = end_idx
                if progress_callback is not None:
                    progress_callback(
                        IngestPhase.DEDUP,
                        dedup_checked,
                        total_chunks,
                        f"{chunks_skipped} skipped",
                    )

                for chunk in batch_chunks:
                    if chunk.note_id not in upserted_note_ids:
                        await self._graph_store.upsert_note(
                            _note_by_id(notes, chunk.note_id)
                        )
                        upserted_note_ids.add(chunk.note_id)

                for chunk in new_chunks:
                    await self._graph_store.upsert_chunk(chunk)
                    chunks_created += 1

                if progress_callback is not None:
                    progress_callback(
                        IngestPhase.UPSERT,
                        chunks_created,
                        total_chunks - chunks_skipped,
                        f"batch {batch_idx + 1}/{num_batches}",
                    )

        if notes and not all_chunks:
            for note in notes:
                await self._graph_store.upsert_note(note)

        return IngestResult(
            notes_parsed=len(notes),
            chunks_created=chunks_created,
            chunks_skipped=chunks_skipped,
            duration_seconds=time.monotonic() - start,
        )


def _note_by_id(notes: list[Note], note_id: UUID) -> Note:
    for note in notes:
        if note.id == note_id:
            return note
    raise ValueError(f"No note found with id {note_id}")
