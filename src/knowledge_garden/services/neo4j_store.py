"""Neo4j implementation of GraphStore.

Uses async Neo4j driver and HNSW vector indexes for similarity search.
All mutations use MERGE for idempotency.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from neo4j import AsyncDriver, AsyncGraphDatabase

from knowledge_garden.config import EmbeddingConfig, Neo4jConfig
from knowledge_garden.services.graph_store import GraphStore

if TYPE_CHECKING:
    from knowledge_garden.models.note import Chunk, Note

logger = logging.getLogger(__name__)


class Neo4jGraphStore(GraphStore):
    """Neo4j implementation using async driver and vector indexes.

    Initialization creates:
    - Uniqueness constraint on Note.id
    - Uniqueness constraint on Chunk.id
    - Vector index on Chunk.embedding (cosine, dimension from config)

    All mutations use MERGE for idempotency.
    """

    def __init__(self, neo4j_config: Neo4jConfig, embedding_config: EmbeddingConfig) -> None:
        self._driver: AsyncDriver = AsyncGraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password),
        )
        self._database = neo4j_config.database
        self._embedding_dim = embedding_config.dimension

    async def initialize(self) -> None:
        """Create constraints and vector index. Idempotent.

        Uses IF NOT EXISTS for constraints (supported in Neo4j 4.4+).
        For the vector index, Neo4j 5.11 requires the db.index.vector.createNodeIndex()
        procedure; idempotency is achieved by checking SHOW INDEXES first.
        """
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "CREATE CONSTRAINT note_id_unique IF NOT EXISTS "
                "FOR (n:Note) REQUIRE n.id IS UNIQUE"
            )

        async with self._driver.session(database=self._database) as session:
            await session.run(
                "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS "
                "FOR (c:Chunk) REQUIRE c.id IS UNIQUE"
            )

        # Vector index creation via procedure (Neo4j 5.11 DDL syntax not yet available).
        # Check for existence first to achieve idempotency.
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                "SHOW INDEXES WHERE name = 'chunk_embeddings'"
            )
            existing = await result.data()

        if not existing:
            async with self._driver.session(database=self._database) as session:
                await session.run(
                    "CALL db.index.vector.createNodeIndex("
                    "$name, $label, $property, $dimension, $similarity_function"
                    ")",
                    name="chunk_embeddings",
                    label="Chunk",
                    property="embedding",
                    dimension=self._embedding_dim,
                    similarity_function="cosine",
                )

        logger.info(
            "Neo4j initialized: constraints and vector index created",
            extra={"database": self._database, "dimension": self._embedding_dim},
        )

    async def close(self) -> None:
        """Close the Neo4j driver."""
        await self._driver.close()
        logger.info("Neo4j driver closed")

    async def upsert_note(self, note: Note) -> None:
        """Insert or update a Note node."""
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "MERGE (n:Note {id: $id}) "
                "SET n.title = $title, n.content = $content, "
                "n.vault = $vault, n.original_path = $original_path",
                id=str(note.id),
                title=note.title,
                content=note.content,
                vault=note.vault,
                original_path=note.original_path,
            )
        logger.info("Note upserted", extra={"note_id": str(note.id), "title": note.title})

    async def upsert_chunk(self, chunk: Chunk) -> None:
        """Insert or update a Chunk node with HAS_CHUNK edge to parent Note."""
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "MERGE (c:Chunk {id: $chunk_id}) "
                "SET c.content = $content, c.heading_context = $heading_context, "
                "c.index = $index, c.embedding = $embedding, c.note_id = $note_id "
                "WITH c "
                "MATCH (n:Note {id: $note_id}) "
                "MERGE (n)-[:HAS_CHUNK]->(c)",
                chunk_id=str(chunk.id),
                content=chunk.content,
                heading_context=chunk.heading_context,
                index=chunk.index,
                embedding=chunk.embedding,
                note_id=str(chunk.note_id),
            )
        logger.info(
            "Chunk upserted",
            extra={"chunk_id": str(chunk.id), "note_id": str(chunk.note_id)},
        )

    async def create_link(
        self, from_note_id: object, to_note_id: object, rel_type: str
    ) -> None:
        """Create a directed relationship between two Notes.

        rel_type: LINKS_TO | RELATED_TO
        Dynamic relationship types are safe here because rel_type is always
        controlled by our code (never user-supplied freeform text).
        """
        query = (
            f"MATCH (a:Note {{id: $from_id}}), (b:Note {{id: $to_id}}) "
            f"MERGE (a)-[:{rel_type}]->(b)"
        )
        async with self._driver.session(database=self._database) as session:
            await session.run(
                query,
                from_id=str(from_note_id),
                to_id=str(to_note_id),
            )
        logger.info(
            "Link created",
            extra={
                "from": str(from_note_id),
                "to": str(to_note_id),
                "rel_type": rel_type,
            },
        )

    async def create_similarity(
        self, chunk_a_id: object, chunk_b_id: object, score: float
    ) -> None:
        """Create a SIMILAR_TO edge between two chunks with a similarity score."""
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "MATCH (a:Chunk {id: $a_id}), (b:Chunk {id: $b_id}) "
                "MERGE (a)-[r:SIMILAR_TO]->(b) "
                "SET r.score = $score",
                a_id=str(chunk_a_id),
                b_id=str(chunk_b_id),
                score=score,
            )
        logger.info(
            "Similarity edge created",
            extra={"chunk_a": str(chunk_a_id), "chunk_b": str(chunk_b_id), "score": score},
        )

    async def find_similar_chunks(
        self, embedding: list[float], limit: int = 20, threshold: float = 0.7
    ) -> list[tuple[Chunk, float]]:
        """Vector similarity search via HNSW index. Returns (chunk, score) pairs."""
        from knowledge_garden.models.note import Chunk as ChunkModel

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                "CALL db.index.vector.queryNodes('chunk_embeddings', $limit, $embedding) "
                "YIELD node, score "
                "WHERE score >= $threshold "
                "RETURN node, score",
                limit=limit,
                embedding=embedding,
                threshold=threshold,
            )
            records = await result.data()

        pairs: list[tuple[Chunk, float]] = []
        for record in records:
            node = record["node"]
            score = record["score"]
            chunk = ChunkModel(
                id=UUID(node["id"]),
                note_id=UUID(node["note_id"]),
                content=node["content"],
                heading_context=node.get("heading_context", ""),
                index=node["index"],
                embedding=list(node["embedding"]) if node.get("embedding") is not None else None,
            )
            pairs.append((chunk, score))

        logger.info("Similar chunks found", extra={"count": len(pairs), "threshold": threshold})
        return pairs

    async def get_note_relationships(self, note_id: object) -> dict[str, list[str]]:
        """Return all LINKS_TO and RELATED_TO targets for a Note.

        Returns a dict keyed by rel_type, each value being a list of target Note ID strings.
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                "MATCH (n:Note {id: $id})-[r:LINKS_TO|RELATED_TO]->(m:Note) "
                "RETURN type(r) AS rel_type, m.id AS target_id",
                id=str(note_id),
            )
            records = await result.data()

        relationships: dict[str, list[str]] = {}
        for record in records:
            rel_type: str = record["rel_type"]
            target_id: str = record["target_id"]
            relationships.setdefault(rel_type, []).append(target_id)

        return relationships

    async def get_all_notes(self) -> list[Note]:
        """Return all Note nodes."""
        from knowledge_garden.models.note import Note as NoteModel

        async with self._driver.session(database=self._database) as session:
            result = await session.run("MATCH (n:Note) RETURN n")
            records = await result.data()

        notes: list[Note] = []
        for record in records:
            node = record["n"]
            note = NoteModel(
                id=UUID(node["id"]),
                title=node["title"],
                content=node["content"],
                vault=node["vault"],
                original_path=node["original_path"],
            )
            notes.append(note)

        logger.info("All notes retrieved", extra={"count": len(notes)})
        return notes

    async def get_chunks_for_note(self, note_id: object) -> list[Chunk]:
        """Return all chunks belonging to a note, ordered by index."""
        from knowledge_garden.models.note import Chunk as ChunkModel

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                "MATCH (n:Note {id: $note_id})-[:HAS_CHUNK]->(c:Chunk) "
                "RETURN c ORDER BY c.index",
                note_id=str(note_id),
            )
            records = await result.data()

        chunks: list[Chunk] = []
        for record in records:
            node = record["c"]
            chunk = ChunkModel(
                id=UUID(node["id"]),
                note_id=UUID(node["note_id"]),
                content=node["content"],
                heading_context=node.get("heading_context", ""),
                index=node["index"],
                embedding=list(node["embedding"]) if node.get("embedding") is not None else None,
            )
            chunks.append(chunk)

        logger.info(
            "Chunks retrieved for note",
            extra={"note_id": str(note_id), "count": len(chunks)},
        )
        return chunks
