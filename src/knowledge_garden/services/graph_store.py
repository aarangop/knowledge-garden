from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge_garden.models.note import Chunk, Note


@dataclass
class SearchResult:
    note_id: str
    title: str
    source_vault: str
    original_path: str
    score: float
    snippet: str
    heading_context: str


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
    async def get_note_relationships_with_scores(
        self, note_id: object
    ) -> dict[str, list[tuple[str, float]]]:
        """Return LINKS_TO and RELATED_TO targets for a Note, each with a score.

        Returns a dict with up to two keys:
          "LINKS_TO"   -> list of (target_note_id_str, 1.0)
          "RELATED_TO" -> list of (target_note_id_str, score)

        A key is absent if there are no relationships of that type.
        """
        ...

    @abstractmethod
    async def get_all_notes(self) -> list[Note]:
        """Return all Note nodes."""
        ...

    @abstractmethod
    async def get_chunks_for_note(self, note_id: object) -> list[Chunk]:
        """Return all chunks belonging to a note, ordered by index."""
        ...

    @abstractmethod
    async def get_all_chunks(self) -> list[Chunk]:
        """Return all Chunk nodes that have embeddings, ordered by note_id then index."""
        ...

    @abstractmethod
    async def clear_semantic_edges(self) -> dict[str, int]:
        """Delete all SIMILAR_TO and RELATED_TO edges. Preserve nodes and LINKS_TO edges.

        Returns a dict with:
            "similarity_edges_deleted" -> int
            "related_to_edges_deleted" -> int
        """
        ...

    @abstractmethod
    async def derive_related_to(self, threshold: float = 0.7) -> int:
        """Derive RELATED_TO edges from SIMILAR_TO chunk edges.

        For each pair of Notes whose chunks have SIMILAR_TO edges above threshold,
        creates a RELATED_TO edge with score = max chunk similarity.
        Returns the number of RELATED_TO edges created/merged.
        """
        ...

    @abstractmethod
    async def get_note_by_id(self, note_id: object) -> Note | None:
        """Return the Note with the given id, or None if it does not exist.

        Args:
            note_id: The UUID of the note (UUID instance or str — coerced to str
                     via str(note_id) before the query).

        Returns:
            Note domain model, or None if no Note with that id exists.
        """
        ...

    @abstractmethod
    async def get_note_by_title(self, title: str) -> Note | None:
        """Return the Note whose title matches the given string (case-insensitive).

        Uses toLower() in Cypher for the comparison so the caller does not need
        to normalise the input.

        Args:
            title: The note title to search for (any casing).

        Returns:
            The matching Note, or None if no note exists with that title.
        """
        ...

    @abstractmethod
    async def get_stats(self) -> dict[str, int | list[str]]:
        """Return graph statistics.

        Returns a dict with exactly the following keys:
            "note_count"            -> int
            "chunk_count"           -> int
            "similarity_edge_count" -> int  (count of SIMILAR_TO edges)
            "related_to_edge_count" -> int  (count of RELATED_TO edges)
            "links_to_edge_count"   -> int  (count of LINKS_TO edges)
            "vault_names"           -> list[str]  (sorted alphabetically, distinct)
        """
        ...

    @abstractmethod
    async def search_notes(
        self,
        query_embedding: list[float],
        limit: int = 10,
        vault_filter: str | None = None,
    ) -> list[SearchResult]:
        """Semantic search: find the most relevant notes for a query embedding.

        Args:
            query_embedding: Pre-computed embedding vector for the query.
            limit: Maximum number of SearchResult objects to return (default 10, max 50).
            vault_filter: If not None, only return notes from this vault.

        Returns:
            list[SearchResult] sorted by score descending, length <= limit.
        """
        ...
