from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from knowledge_garden.config import VaultConfig
from knowledge_garden.services.chunker import NoteChunker
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.parser import MarkdownParser

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class IngestResult:
    notes_parsed: int
    chunks_created: int
    duration_seconds: float


class IngestPipeline:
    def __init__(
        self,
        parser: MarkdownParser,
        chunker: NoteChunker,
        embedder: EmbeddingService,
        graph_store: GraphStore,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._graph_store = graph_store

    async def run(
        self,
        vault_config: VaultConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestResult:
        start = time.monotonic()

        notes = self._parser.parse_vault(vault_config)
        total = len(notes)

        all_chunks = []
        for i, note in enumerate(notes, start=1):
            if progress_callback is not None:
                progress_callback(i, total, note.title)
            all_chunks.extend(self._chunker.chunk_note(note))

        if all_chunks:
            texts = [chunk.content for chunk in all_chunks]
            vectors = await self._embedder.embed(texts)
            for chunk, vector in zip(all_chunks, vectors, strict=True):
                chunk.embedding = vector

        for note in notes:
            await self._graph_store.upsert_note(note)
        for chunk in all_chunks:
            await self._graph_store.upsert_chunk(chunk)

        return IngestResult(
            notes_parsed=len(notes),
            chunks_created=len(all_chunks),
            duration_seconds=time.monotonic() - start,
        )
