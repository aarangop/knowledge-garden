from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge_garden.models.note import Chunk, Note


class GraphStore(ABC):
    """Abstract graph storage backend."""

    @abstractmethod
    async def initialize(self) -> None:
        """Create indexes, constraints, vector indexes."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    async def upsert_note(self, note: Note) -> None:
        """Insert or update a Note node."""
        ...

    @abstractmethod
    async def upsert_chunk(self, chunk: Chunk) -> None:
        """Insert or update a Chunk node with HAS_CHUNK edge to parent Note."""
        ...

    @abstractmethod
    async def create_link(self, from_note_id: object, to_note_id: object, rel_type: str) -> None:
        """Create a directed relationship between two Notes.

        rel_type: LINKS_TO | RELATED_TO
        """
        ...

    @abstractmethod
    async def create_similarity(
        self, chunk_a_id: object, chunk_b_id: object, score: float
    ) -> None:
        """Create a SIMILAR_TO edge between two chunks with a similarity score."""
        ...

    @abstractmethod
    async def find_similar_chunks(
        self, embedding: list[float], limit: int = 20, threshold: float = 0.7
    ) -> list[tuple[Chunk, float]]:
        """Vector similarity search via HNSW index. Returns (chunk, score) pairs."""
        ...

    @abstractmethod
    async def get_note_relationships(self, note_id: object) -> dict[str, list[str]]:
        """Return all LINKS_TO and RELATED_TO targets for a Note."""
        ...

    @abstractmethod
    async def get_all_notes(self) -> list[Note]:
        """Return all Note nodes."""
        ...

    @abstractmethod
    async def get_chunks_for_note(self, note_id: object) -> list[Chunk]:
        """Return all chunks belonging to a note, ordered by index."""
        ...
