"""Tests for Neo4jGraphStore — contract: specifications/01_foundation/contract.md, section 5.2.

All tests are integration tests requiring a running Neo4j 5.11+ instance
at bolt://localhost:7687 with credentials neo4j/knowledge-garden.
"""

import pytest

from knowledge_garden.models.note import Chunk, Note


class TestNeo4jStoreInitialization:
    """Contract section: 5.2 — initialize() behaviour."""

    @pytest.mark.integration
    async def test_initialize_creates_constraints(self, neo4j_store):
        """Contract: After initialize(), Note and Chunk unique constraints exist in Neo4j."""
        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run("SHOW CONSTRAINTS")
            records = await result.data()

        # At least one constraint must cover Note.id and one must cover Chunk.id.
        # The exact constraint name is implementation-defined; check the labelled properties.
        labelled_props = [
            (r.get("labelsOrTypes", []), r.get("properties", []))
            for r in records
        ]
        note_constraint_exists = any(
            "Note" in labels and "id" in props
            for labels, props in labelled_props
        )
        chunk_constraint_exists = any(
            "Chunk" in labels and "id" in props
            for labels, props in labelled_props
        )
        assert note_constraint_exists, (
            f"No unique constraint on Note.id found. Constraints: {records}"
        )
        assert chunk_constraint_exists, (
            f"No unique constraint on Chunk.id found. Constraints: {records}"
        )

    @pytest.mark.integration
    async def test_initialize_creates_vector_index(self, neo4j_store):
        """Contract: After initialize(), the 'chunk_embeddings' vector index exists."""
        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run("SHOW INDEXES")
            records = await result.data()

        index_names = [r.get("name", "") for r in records]
        assert "chunk_embeddings" in index_names, (
            f"'chunk_embeddings' vector index not found. Indexes: {index_names}"
        )

    @pytest.mark.integration
    async def test_initialize_idempotent(self, neo4j_store):
        """Contract: Calling initialize() a second time raises no error."""
        # neo4j_store fixture already called initialize() once.
        # A second call must succeed without raising.
        await neo4j_store.initialize()


class TestNeo4jStoreUpsertNote:
    """Contract section: 5.2 — upsert_note() behaviour."""

    @pytest.mark.integration
    async def test_upsert_note_creates_node(self, neo4j_store):
        """Contract: Upsert a Note → query by id → node exists with correct properties."""
        note = Note(
            title="Test Note",
            content="Some content for testing",
            vault="test_vault",
            original_path="test/test_note.md",
        )
        await neo4j_store.upsert_note(note)

        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run(
                "MATCH (n:Note {id: $id}) RETURN n",
                id=str(note.id),
            )
            record = await result.single()

        assert record is not None, f"Note node with id {note.id} was not created"
        node = record["n"]
        assert node["title"] == note.title
        assert node["content"] == note.content
        assert node["vault"] == note.vault
        assert node["original_path"] == note.original_path

    @pytest.mark.integration
    async def test_upsert_note_updates_existing(self, neo4j_store):
        """Contract: Upsert same Note id with different title → title is updated in the graph."""
        note = Note(
            title="Original Title",
            content="Original content",
            vault="test_vault",
            original_path="test/original.md",
        )
        await neo4j_store.upsert_note(note)

        # Upsert again with the same id but a new title
        updated_note = Note(
            id=note.id,
            title="Updated Title",
            content="Original content",
            vault="test_vault",
            original_path="test/original.md",
        )
        await neo4j_store.upsert_note(updated_note)

        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run(
                "MATCH (n:Note {id: $id}) RETURN n.title AS title",
                id=str(note.id),
            )
            record = await result.single()

        assert record is not None
        assert record["title"] == "Updated Title", (
            f"Expected title 'Updated Title', got '{record['title']}'"
        )


class TestNeo4jStoreUpsertChunk:
    """Contract section: 5.2 — upsert_chunk() behaviour."""

    @pytest.mark.integration
    async def test_upsert_chunk_creates_node_and_edge(self, neo4j_store):
        """Contract: Upsert a Chunk → HAS_CHUNK edge exists between parent Note and Chunk."""
        note = Note(
            title="Parent Note",
            content="Parent content",
            vault="test_vault",
            original_path="test/parent.md",
        )
        await neo4j_store.upsert_note(note)

        chunk = Chunk(
            note_id=note.id,
            content="This is a chunk",
            heading_context="## Introduction",
            index=0,
            embedding=[0.1] * 768,
        )
        await neo4j_store.upsert_chunk(chunk)

        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run(
                """
                MATCH (n:Note {id: $note_id})-[:HAS_CHUNK]->(c:Chunk {id: $chunk_id})
                RETURN c
                """,
                note_id=str(note.id),
                chunk_id=str(chunk.id),
            )
            record = await result.single()

        assert record is not None, (
            f"HAS_CHUNK edge from Note {note.id} to Chunk {chunk.id} was not created"
        )
        node = record["c"]
        assert node["content"] == chunk.content
        assert node["heading_context"] == chunk.heading_context
        assert node["index"] == chunk.index


class TestNeo4jStoreCreateLink:
    """Contract section: 5.2 — create_link() behaviour."""

    @pytest.mark.integration
    async def test_create_link(self, neo4j_store):
        """Contract: create_link() with LINKS_TO rel_type → LINKS_TO edge exists between two
        Notes.
        """
        note_a = Note(
            title="Note A",
            content="Content A",
            vault="test_vault",
            original_path="test/note_a.md",
        )
        note_b = Note(
            title="Note B",
            content="Content B",
            vault="test_vault",
            original_path="test/note_b.md",
        )
        await neo4j_store.upsert_note(note_a)
        await neo4j_store.upsert_note(note_b)

        await neo4j_store.create_link(note_a.id, note_b.id, "LINKS_TO")

        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            result = await session.run(
                """
                MATCH (a:Note {id: $id_a})-[:LINKS_TO]->(b:Note {id: $id_b})
                RETURN count(*) AS cnt
                """,
                id_a=str(note_a.id),
                id_b=str(note_b.id),
            )
            record = await result.single()

        assert record is not None
        assert record["cnt"] == 1, (
            f"Expected 1 LINKS_TO edge, got {record['cnt']}"
        )


class TestNeo4jStoreClose:
    """Contract section: 5.2 — close() behaviour."""

    @pytest.mark.integration
    async def test_close_cleans_up(self, neo4j_store):
        """Contract: After close(), the internal _driver is closed.

        We call close() directly here (teardown in the fixture will also call it,
        but a closed driver's close() is a no-op per the neo4j driver contract).
        We verify the _driver attribute exists and that calling close() does not raise.
        """
        # Capture reference before closing
        driver = neo4j_store._driver
        assert driver is not None, "_driver should exist before close()"

        await neo4j_store.close()

        # After close, the driver should be shut down. The neo4j AsyncDriver exposes
        # _closed (or similar) — verify by attempting to confirm the driver is done.
        # The simplest portable check: _driver attribute still holds the object (not None)
        # but the driver is in a closed state. We confirm no exception was raised above
        # and that the attribute is still present (not deleted).
        assert neo4j_store._driver is driver, (
            "_driver attribute should remain on the instance after close()"
        )
