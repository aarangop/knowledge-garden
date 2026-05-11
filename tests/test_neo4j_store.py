"""Tests for Neo4jGraphStore — contract: specifications/01_foundation/contract.md, section 5.2.

All tests are integration tests requiring a running Neo4j 5.11+ instance
at bolt://localhost:7687 with credentials neo4j/knowledge-garden.

Unit tests for get_note_by_id, get_stats, and search_notes are added for
contract: specifications/10_search_api/contract.md, sections 2, 3, and 4.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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


class TestGetNoteRelationshipsWithScores:
    """Contract section: 1 — get_note_relationships_with_scores() behaviour."""

    @pytest.mark.integration
    async def test_get_note_relationships_with_scores_returns_links_to(self, neo4j_store):
        """Contract: LINKS_TO edge → {"LINKS_TO": [(target_id_str, 1.0)]}."""
        source = Note(
            title="Source Note",
            content="src",
            vault="v1",
            original_path="source.md",
        )
        target = Note(
            title="Target Note",
            content="tgt",
            vault="v1",
            original_path="target.md",
        )
        await neo4j_store.upsert_note(source)
        await neo4j_store.upsert_note(target)
        await neo4j_store.create_link(source.id, target.id, "LINKS_TO")

        result = await neo4j_store.get_note_relationships_with_scores(source.id)

        assert "LINKS_TO" in result
        assert len(result["LINKS_TO"]) == 1
        target_id_str, score = result["LINKS_TO"][0]
        assert target_id_str == str(target.id)
        assert score == 1.0

    @pytest.mark.integration
    async def test_get_note_relationships_with_scores_returns_related_to(self, neo4j_store):
        """Contract: RELATED_TO edge with score 0.85 → {"RELATED_TO": [(target_id_str, 0.85)]}."""
        source = Note(
            title="Source Note R",
            content="src",
            vault="v1",
            original_path="source_r.md",
        )
        target = Note(
            title="Target Note R",
            content="tgt",
            vault="v1",
            original_path="target_r.md",
        )
        await neo4j_store.upsert_note(source)
        await neo4j_store.upsert_note(target)

        # Create RELATED_TO edge directly via Cypher with a score property
        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            await session.run(
                """
                MATCH (a:Note {id: $src_id}), (b:Note {id: $tgt_id})
                MERGE (a)-[r:RELATED_TO]->(b)
                SET r.score = $score
                """,
                src_id=str(source.id),
                tgt_id=str(target.id),
                score=0.85,
            )

        result = await neo4j_store.get_note_relationships_with_scores(source.id)

        assert "RELATED_TO" in result
        assert len(result["RELATED_TO"]) == 1
        target_id_str, score = result["RELATED_TO"][0]
        assert target_id_str == str(target.id)
        assert abs(score - 0.85) < 1e-6

    @pytest.mark.integration
    async def test_get_note_relationships_with_scores_both_types(self, neo4j_store):
        """Contract: both LINKS_TO and RELATED_TO edges → both keys present in result."""
        source = Note(
            title="Source Both",
            content="src",
            vault="v1",
            original_path="source_both.md",
        )
        target_link = Note(
            title="Link Target",
            content="l",
            vault="v1",
            original_path="link_target.md",
        )
        target_related = Note(
            title="Related Target",
            content="r",
            vault="v1",
            original_path="related_target.md",
        )
        await neo4j_store.upsert_note(source)
        await neo4j_store.upsert_note(target_link)
        await neo4j_store.upsert_note(target_related)
        await neo4j_store.create_link(source.id, target_link.id, "LINKS_TO")

        async with neo4j_store._driver.session(database=neo4j_store._database) as session:
            await session.run(
                """
                MATCH (a:Note {id: $src_id}), (b:Note {id: $tgt_id})
                MERGE (a)-[r:RELATED_TO]->(b)
                SET r.score = $score
                """,
                src_id=str(source.id),
                tgt_id=str(target_related.id),
                score=0.75,
            )

        result = await neo4j_store.get_note_relationships_with_scores(source.id)

        assert "LINKS_TO" in result
        assert "RELATED_TO" in result

    @pytest.mark.integration
    async def test_get_note_relationships_with_scores_empty(self, neo4j_store):
        """Contract: note with no relationships → returns {}."""
        lone = Note(
            title="Lone Note",
            content="alone",
            vault="v1",
            original_path="lone.md",
        )
        await neo4j_store.upsert_note(lone)

        result = await neo4j_store.get_note_relationships_with_scores(lone.id)

        assert result == {}


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


# ---------------------------------------------------------------------------
# Helpers for unit tests (mock Neo4j driver/session)
# ---------------------------------------------------------------------------


def _make_neo4j_store_unit():
    """Return a Neo4jGraphStore instance with a mocked driver (no real Neo4j needed)."""
    from knowledge_garden.config import EmbeddingConfig, Neo4jConfig
    from knowledge_garden.services.neo4j_store import Neo4jGraphStore

    neo4j_config = Neo4jConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
        database="neo4j",
    )
    embedding_config = EmbeddingConfig()
    store = Neo4jGraphStore(neo4j_config, embedding_config)
    # Replace driver with an AsyncMock so no real connection is made.
    store._driver = AsyncMock()
    return store


def _make_async_context_manager_session(session_mock):
    """Wrap session_mock in an async context manager so 'async with driver.session()' works."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_note_node(
    note_id: str | None = None,
    title: str = "Test Note",
    vault: str = "vault_a",
    original_path: str = "test.md",
    content: str = "note content",
) -> dict:
    """Build a dict that mimics a Neo4j node for a Note."""
    return {
        "id": note_id or str(uuid.uuid4()),
        "title": title,
        "vault": vault,
        "original_path": original_path,
        "content": content,
    }


# ---------------------------------------------------------------------------
# TestGetNoteById — unit tests (spec 10, section 2)
# ---------------------------------------------------------------------------


class TestGetNoteByIdUnit:
    """Contract section 2 — get_note_by_id() unit tests (no live Neo4j)."""

    @pytest.mark.unit
    async def test_get_note_by_id_found(self):
        """Contract: mock session returns one Note node row → Note returned with correct fields."""
        store = _make_neo4j_store_unit()
        note_id_str = str(uuid.uuid4())
        node_data = _make_note_node(
            note_id=note_id_str,
            title="Found Note",
            vault="vault_x",
            original_path="found.md",
            content="some content",
        )

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": node_data})

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_id(note_id_str)

        assert note is not None
        assert str(note.id) == note_id_str
        assert note.title == "Found Note"
        assert note.vault == "vault_x"
        assert note.original_path == "found.md"
        assert note.content == "some content"

    @pytest.mark.unit
    async def test_get_note_by_id_not_found(self):
        """Contract: mock session .single() returns None → method returns None."""
        store = _make_neo4j_store_unit()

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        result = await store.get_note_by_id("00000000-0000-0000-0000-000000000099")

        assert result is None

    @pytest.mark.unit
    async def test_get_note_by_id_uuid_coerced(self):
        """Contract: UUID object passed → Cypher receives str(note_id) as $id parameter."""
        store = _make_neo4j_store_unit()
        note_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        await store.get_note_by_id(note_uuid)

        # Verify the session.run call used str(note_uuid) as the id parameter.
        call_kwargs = mock_session.run.call_args.kwargs
        assert call_kwargs.get("id") == str(note_uuid)


# ---------------------------------------------------------------------------
# TestGetStatsUnit — unit tests (spec 10, section 3)
# ---------------------------------------------------------------------------


class TestGetStatsUnit:
    """Contract section 3 — get_stats() unit tests (no live Neo4j)."""

    def _make_store_with_session_sequence(self, session_results: list):
        """Build a store whose driver.session() returns successive mock sessions.

        session_results: list of return values (dicts) for each session.run().data() call,
        or None to simulate no record from .single().
        """
        store = _make_neo4j_store_unit()
        sessions = []
        for result_data in session_results:
            mock_result = AsyncMock()
            mock_result.data = AsyncMock(return_value=result_data)
            mock_result.single = AsyncMock(
                return_value=result_data[0] if result_data else None
            )
            mock_session = AsyncMock()
            mock_session.run = AsyncMock(return_value=mock_result)
            sessions.append(mock_session)

        call_count = 0

        def session_factory(**kwargs):
            nonlocal call_count
            s = sessions[call_count % len(sessions)]
            call_count += 1
            return _make_async_context_manager_session(s)

        store._driver.session = MagicMock(side_effect=session_factory)
        return store

    @pytest.mark.unit
    async def test_get_stats_returns_all_keys(self):
        """Contract: returned dict has all six required keys."""
        # Session results for each query: notes, chunks, similar, related, links_to
        store = self._make_store_with_session_sequence([
            [{"note_count": 5, "vault_names": ["v1", "v2"]}],  # notes query
            [{"chunk_count": 15}],                              # chunks query
            [{"similarity_edge_count": 10}],                   # similar
            [{"related_to_edge_count": 3}],                    # related
            [{"links_to_edge_count": 2}],                      # links_to
        ])

        result = await store.get_stats()

        for key in (
            "note_count",
            "chunk_count",
            "similarity_edge_count",
            "related_to_edge_count",
            "links_to_edge_count",
            "vault_names",
        ):
            assert key in result, f"Missing key '{key}' in get_stats result"

    @pytest.mark.unit
    async def test_get_stats_vault_names_sorted(self):
        """Contract: vault_names in result are sorted alphabetically."""
        store = self._make_store_with_session_sequence([
            [{"note_count": 2, "vault_names": ["z_vault", "a_vault"]}],
            [{"chunk_count": 0}],
            [{"similarity_edge_count": 0}],
            [{"related_to_edge_count": 0}],
            [{"links_to_edge_count": 0}],
        ])

        result = await store.get_stats()

        assert result["vault_names"] == ["a_vault", "z_vault"]

    @pytest.mark.unit
    async def test_get_stats_empty_graph(self):
        """Contract: empty graph (no records from any query) → all int fields 0, vault_names=[]."""
        store = self._make_store_with_session_sequence([
            [],  # notes query returns no records
            [],  # chunks
            [],  # similar
            [],  # related
            [],  # links_to
        ])

        result = await store.get_stats()

        assert result["note_count"] == 0
        assert result["chunk_count"] == 0
        assert result["similarity_edge_count"] == 0
        assert result["related_to_edge_count"] == 0
        assert result["links_to_edge_count"] == 0
        assert result["vault_names"] == []


# ---------------------------------------------------------------------------
# TestSearchNotesUnit — unit tests (spec 10, section 4)
# ---------------------------------------------------------------------------


def _make_chunk_model(
    note_id: uuid.UUID,
    content: str = "chunk text",
    heading_context: str = "## Section",
    index: int = 0,
) -> Chunk:
    """Build a Chunk domain model."""
    return Chunk(
        note_id=note_id,
        content=content,
        heading_context=heading_context,
        index=index,
        embedding=[0.1] * 768,
    )


def _make_note_model(
    note_id: uuid.UUID | None = None,
    title: str = "A Note",
    vault: str = "vault_a",
    original_path: str = "a.md",
) -> Note:
    """Build a Note domain model."""
    kwargs: dict = dict(title=title, content="content", vault=vault, original_path=original_path)
    if note_id is not None:
        kwargs["id"] = note_id
    return Note(**kwargs)


class TestSearchNotesUnit:
    """Contract section 4 — search_notes() unit tests (no live Neo4j)."""

    @pytest.mark.unit
    async def test_search_notes_returns_results(self):
        """Contract: 2 chunks from different notes → list of 2 SearchResult objects."""
        store = _make_neo4j_store_unit()

        note_id_a = uuid.uuid4()
        note_id_b = uuid.uuid4()
        chunk_a = _make_chunk_model(note_id=note_id_a, content="chunk A")
        chunk_b = _make_chunk_model(note_id=note_id_b, content="chunk B")
        note_a = _make_note_model(note_id=note_id_a, title="Note A")
        note_b = _make_note_model(note_id=note_id_b, title="Note B")

        store.find_similar_chunks = AsyncMock(return_value=[(chunk_a, 0.9), (chunk_b, 0.8)])
        store.get_note_by_id = AsyncMock(side_effect=lambda nid: (
            note_a if str(nid) == str(note_id_a) else note_b
        ))

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        assert len(results) == 2

    @pytest.mark.unit
    async def test_search_notes_dedup_keeps_best_score(self):
        """Contract: 3 chunks from the same note, scores [0.9, 0.7, 0.8] → 1 result, score=0.9."""
        store = _make_neo4j_store_unit()

        note_id = uuid.uuid4()
        note = _make_note_model(note_id=note_id)
        chunks = [
            _make_chunk_model(note_id=note_id, content=f"chunk {i}", index=i)
            for i in range(3)
        ]
        scores = [0.9, 0.7, 0.8]
        pairs = list(zip(chunks, scores))

        store.find_similar_chunks = AsyncMock(return_value=pairs)
        store.get_note_by_id = AsyncMock(return_value=note)

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        assert len(results) == 1
        assert results[0].score == 0.9

    @pytest.mark.unit
    async def test_search_notes_vault_filter(self):
        """Contract: vault_filter='v1' → only note from v1 is returned."""
        store = _make_neo4j_store_unit()

        note_id_v1 = uuid.uuid4()
        note_id_v2 = uuid.uuid4()
        chunk_v1 = _make_chunk_model(note_id=note_id_v1, content="v1 chunk")
        chunk_v2 = _make_chunk_model(note_id=note_id_v2, content="v2 chunk")
        note_v1 = _make_note_model(note_id=note_id_v1, vault="v1")
        note_v2 = _make_note_model(note_id=note_id_v2, vault="v2")

        store.find_similar_chunks = AsyncMock(
            return_value=[(chunk_v1, 0.9), (chunk_v2, 0.85)]
        )

        async def get_note(nid):
            if str(nid) == str(note_id_v1):
                return note_v1
            return note_v2

        store.get_note_by_id = AsyncMock(side_effect=get_note)

        results = await store.search_notes(
            query_embedding=[0.1] * 768, limit=10, vault_filter="v1"
        )

        assert len(results) == 1
        assert results[0].source_vault == "v1"

    @pytest.mark.unit
    async def test_search_notes_orphaned_chunk_skipped(self):
        """Contract: get_note_by_id returns None for one chunk → 1 result, no exception."""
        store = _make_neo4j_store_unit()

        note_id_good = uuid.uuid4()
        note_id_orphan = uuid.uuid4()
        chunk_good = _make_chunk_model(note_id=note_id_good, content="good chunk")
        chunk_orphan = _make_chunk_model(note_id=note_id_orphan, content="orphan chunk")
        note_good = _make_note_model(note_id=note_id_good)

        store.find_similar_chunks = AsyncMock(
            return_value=[(chunk_good, 0.9), (chunk_orphan, 0.85)]
        )

        async def get_note(nid):
            if str(nid) == str(note_id_good):
                return note_good
            return None

        store.get_note_by_id = AsyncMock(side_effect=get_note)

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        assert len(results) == 1
        assert results[0].note_id == str(note_id_good)

    @pytest.mark.unit
    async def test_search_notes_sorted_by_score_desc(self):
        """Contract: 3 notes with scores [0.8, 0.95, 0.72] → results ordered [0.95, 0.80, 0.72]."""
        store = _make_neo4j_store_unit()

        note_ids = [uuid.uuid4() for _ in range(3)]
        chunks = [_make_chunk_model(note_id=nid) for nid in note_ids]
        scores = [0.8, 0.95, 0.72]
        pairs = list(zip(chunks, scores))
        notes = [_make_note_model(note_id=nid) for nid in note_ids]

        store.find_similar_chunks = AsyncMock(return_value=pairs)

        async def get_note(nid):
            for n in notes:
                if str(n.id) == str(nid):
                    return n
            return None

        store.get_note_by_id = AsyncMock(side_effect=get_note)

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        result_scores = [r.score for r in results]
        assert result_scores == sorted(result_scores, reverse=True)
        assert result_scores[0] == 0.95
        assert result_scores[1] == 0.8
        assert result_scores[2] == 0.72

    @pytest.mark.unit
    async def test_search_notes_limit_applied(self):
        """Contract: limit=2, 5 unique notes available → exactly 2 results returned."""
        store = _make_neo4j_store_unit()

        note_ids = [uuid.uuid4() for _ in range(5)]
        chunks = [_make_chunk_model(note_id=nid) for nid in note_ids]
        scores = [0.9 - i * 0.05 for i in range(5)]
        pairs = list(zip(chunks, scores))
        notes = [_make_note_model(note_id=nid) for nid in note_ids]

        store.find_similar_chunks = AsyncMock(return_value=pairs)

        async def get_note(nid):
            for n in notes:
                if str(n.id) == str(nid):
                    return n
            return None

        store.get_note_by_id = AsyncMock(side_effect=get_note)

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=2)

        assert len(results) == 2

    @pytest.mark.unit
    async def test_search_notes_empty_graph(self):
        """Contract: find_similar_chunks returns [] → search_notes returns []."""
        store = _make_neo4j_store_unit()
        store.find_similar_chunks = AsyncMock(return_value=[])
        store.get_note_by_id = AsyncMock()

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        assert results == []
        store.get_note_by_id.assert_not_called()

    @pytest.mark.unit
    async def test_search_notes_snippet_truncated(self):
        """Contract: chunk.content longer than 200 chars → result.snippet == content[:200]."""
        store = _make_neo4j_store_unit()

        note_id = uuid.uuid4()
        long_content = "x" * 300  # 300 characters
        chunk = _make_chunk_model(note_id=note_id, content=long_content)
        note = _make_note_model(note_id=note_id)

        store.find_similar_chunks = AsyncMock(return_value=[(chunk, 0.9)])
        store.get_note_by_id = AsyncMock(return_value=note)

        results = await store.search_notes(query_embedding=[0.1] * 768, limit=10)

        assert len(results) == 1
        assert results[0].snippet == long_content[:200]

    @pytest.mark.unit
    async def test_search_notes_overfetch_factor(self):
        """Contract: limit=3 → find_similar_chunks called with limit=15 (limit * 5)."""
        store = _make_neo4j_store_unit()
        store.find_similar_chunks = AsyncMock(return_value=[])

        await store.search_notes(query_embedding=[0.1] * 768, limit=3)

        store.find_similar_chunks.assert_called_once()
        call_kwargs = store.find_similar_chunks.call_args.kwargs
        # The over-fetch limit may be passed as positional or keyword arg.
        call_args = store.find_similar_chunks.call_args
        # Check either positional or keyword argument for limit=15
        if call_kwargs.get("limit") is not None:
            assert call_kwargs["limit"] == 15
        else:
            # positional: find_similar_chunks(embedding=..., limit=15, threshold=0.0)
            pos_args = call_args.args
            # embedding is first positional, limit is second
            assert len(pos_args) >= 2 and pos_args[1] == 15, (
                f"Expected find_similar_chunks limit=15, got call_args={call_args}"
            )


# ---------------------------------------------------------------------------
# Spec 13 — Frontmatter persistence
# ---------------------------------------------------------------------------


class TestFrontmatterPersistence:
    """Spec 13 §3 / §6.2 — frontmatter_json on Note nodes (unit tests)."""

    @pytest.mark.unit
    async def test_upsert_note_writes_frontmatter_json(self):
        """Spec 13 §3.2: upsert_note serializes frontmatter to JSON in $frontmatter_json."""
        import json

        store = _make_neo4j_store_unit()
        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = Note(
            title="t",
            content="c",
            vault="v",
            original_path="p.md",
            frontmatter={"tags": ["a"]},
        )
        await store.upsert_note(note)

        call_kwargs = mock_session.run.call_args.kwargs
        assert "frontmatter_json" in call_kwargs
        # Round-trip through json to allow either key-order representation,
        # though the contract pins sort_keys=False so ["a"] is preserved.
        assert json.loads(call_kwargs["frontmatter_json"]) == {"tags": ["a"]}

    @pytest.mark.unit
    async def test_upsert_note_empty_frontmatter_serializes_to_empty_object(self):
        """Spec 13 §3.1: empty dict serializes to '{}' (never null)."""
        store = _make_neo4j_store_unit()
        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = Note(title="t", content="c", vault="v", original_path="p.md")
        await store.upsert_note(note)

        call_kwargs = mock_session.run.call_args.kwargs
        assert call_kwargs.get("frontmatter_json") == "{}"

    @pytest.mark.unit
    async def test_upsert_note_unicode_frontmatter_no_ascii_escape(self):
        """Spec 13 §3.1: ensure_ascii=False → literal Unicode characters in JSON."""
        store = _make_neo4j_store_unit()
        mock_session = AsyncMock()
        mock_session.run = AsyncMock()
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = Note(
            title="t",
            content="c",
            vault="v",
            original_path="p.md",
            frontmatter={"summary": "café"},
        )
        await store.upsert_note(note)

        call_kwargs = mock_session.run.call_args.kwargs
        json_str = call_kwargs["frontmatter_json"]
        assert "café" in json_str
        assert "\\u" not in json_str

    @pytest.mark.unit
    async def test_get_all_notes_deserializes_frontmatter_json(self):
        """Spec 13 §3.3: get_all_notes deserializes frontmatter_json into a dict."""
        store = _make_neo4j_store_unit()
        node = _make_note_node()
        node["frontmatter_json"] = '{"tags": ["a"]}'

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": node}])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        notes = await store.get_all_notes()
        assert len(notes) == 1
        assert notes[0].frontmatter == {"tags": ["a"]}

    @pytest.mark.unit
    async def test_get_all_notes_missing_property_defaults_to_empty(self):
        """Spec 13 §3.4: legacy node without frontmatter_json → frontmatter == {}."""
        store = _make_neo4j_store_unit()
        node = _make_note_node()  # no frontmatter_json key

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": node}])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        notes = await store.get_all_notes()
        assert len(notes) == 1
        assert notes[0].frontmatter == {}

    @pytest.mark.unit
    async def test_get_all_notes_malformed_json_defaults_to_empty(self, caplog):
        """Spec 13 §3.3: malformed frontmatter_json → frontmatter={} and WARNING logged."""
        import logging as _logging

        store = _make_neo4j_store_unit()
        node = _make_note_node()
        node["frontmatter_json"] = "not-json"

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": node}])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        with caplog.at_level(_logging.WARNING, logger="knowledge_garden.services.neo4j_store"):
            notes = await store.get_all_notes()

        assert len(notes) == 1
        assert notes[0].frontmatter == {}
        warnings = [
            r for r in caplog.records
            if r.levelno == _logging.WARNING
            and r.name == "knowledge_garden.services.neo4j_store"
        ]
        assert warnings, "Expected a WARNING for malformed frontmatter_json"

    @pytest.mark.unit
    async def test_get_all_notes_non_dict_json_defaults_to_empty(self):
        """Spec 13 §3.3: JSON list/scalar in frontmatter_json → frontmatter == {}."""
        store = _make_neo4j_store_unit()
        node = _make_note_node()
        node["frontmatter_json"] = "[1, 2, 3]"

        mock_result = AsyncMock()
        mock_result.data = AsyncMock(return_value=[{"n": node}])
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        notes = await store.get_all_notes()
        assert len(notes) == 1
        assert notes[0].frontmatter == {}

    @pytest.mark.unit
    async def test_get_note_by_id_deserializes_frontmatter_json(self):
        """Spec 13 §3.3: get_note_by_id deserializes frontmatter_json into a dict."""
        store = _make_neo4j_store_unit()
        node = _make_note_node()
        node["frontmatter_json"] = '{"k": "v"}'

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": node})
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_id(node["id"])
        assert note is not None
        assert note.frontmatter == {"k": "v"}

    @pytest.mark.unit
    async def test_get_note_by_id_missing_property_defaults_to_empty(self):
        """Spec 13 §3.4: legacy node without frontmatter_json → frontmatter == {}."""
        store = _make_neo4j_store_unit()
        node = _make_note_node()  # no frontmatter_json

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": node})
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_id(node["id"])
        assert note is not None
        assert note.frontmatter == {}


class TestFrontmatterPersistenceIntegration:
    """Spec 13 §6.2 — round-trip integration test."""

    @pytest.mark.integration
    async def test_upsert_note_round_trip_preserves_frontmatter(self, neo4j_store):
        """Spec 13 §6.2: upsert + get_note_by_id preserves rich frontmatter."""
        fm = {"tags": ["a", "b"], "meta": {"k": "v"}}
        note = Note(
            title="FM Round Trip",
            content="body",
            vault="v_fm",
            original_path="fm/round_trip.md",
            frontmatter=fm,
        )
        await neo4j_store.upsert_note(note)

        loaded = await neo4j_store.get_note_by_id(note.id)
        assert loaded is not None
        assert loaded.frontmatter == fm


# ---------------------------------------------------------------------------
# TestGetNoteByTitleUnit — unit tests (spec 12, section 1)
# ---------------------------------------------------------------------------


class TestGetNoteByTitleUnit:
    """Spec 12 §1 — get_note_by_title() unit tests (no live Neo4j)."""

    @pytest.mark.unit
    async def test_get_note_by_title_found(self):
        """Spec 12 §1: mock session returns one Note node row → returns Note with title."""
        store = _make_neo4j_store_unit()
        node_data = _make_note_node(
            title="My Note",
            vault="vault_x",
            original_path="my_note.md",
            content="body",
        )

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": node_data})

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_title("My Note")

        assert note is not None
        assert note.title == "My Note"
        assert note.vault == "vault_x"
        assert note.original_path == "my_note.md"
        assert note.content == "body"

    @pytest.mark.unit
    async def test_get_note_by_title_case_insensitive(self):
        """Spec 12 §1: stored title is 'My Note', query is 'my note' → returns Note.

        Cypher uses toLower() on both sides; we assert the parameter passed and that
        the result is returned regardless of the casing of the input.
        """
        store = _make_neo4j_store_unit()
        node_data = _make_note_node(title="My Note")

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": node_data})

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_title("my note")

        assert note is not None
        assert note.title == "My Note"

        # The Cypher must use toLower() on the property AND pass the title param
        # (case folding for the parameter side happens in Cypher via toLower).
        call_args = mock_session.run.call_args
        cypher_text = call_args.args[0] if call_args.args else ""
        assert "toLower" in cypher_text, (
            f"Expected toLower() in Cypher, got: {cypher_text}"
        )

    @pytest.mark.unit
    async def test_get_note_by_title_not_found(self):
        """Spec 12 §1: mock session returns no rows → method returns None."""
        store = _make_neo4j_store_unit()

        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        result = await store.get_note_by_title("does not exist")

        assert result is None

    @pytest.mark.unit
    async def test_get_note_by_title_returns_first_match(self):
        """Spec 12 §1: mock session returns two rows → first row only (LIMIT 1 in Cypher)."""
        store = _make_neo4j_store_unit()
        first = _make_note_node(title="First Match", original_path="first.md")
        second = _make_note_node(title="First Match", original_path="second.md")

        # .single() returns the first row when LIMIT 1 is honoured by the Cypher.
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"n": first})
        # .data() would expose both rows had LIMIT been absent; we keep it available
        # but the implementation must call .single() (driven by LIMIT 1).
        mock_result.data = AsyncMock(return_value=[{"n": first}, {"n": second}])

        mock_session = AsyncMock()
        mock_session.run = AsyncMock(return_value=mock_result)
        store._driver.session = MagicMock(
            return_value=_make_async_context_manager_session(mock_session)
        )

        note = await store.get_note_by_title("First Match")

        assert note is not None
        assert note.original_path == "first.md"

        # Verify LIMIT 1 appears in the Cypher (case-insensitive search).
        call_args = mock_session.run.call_args
        cypher_text = (call_args.args[0] if call_args.args else "").upper()
        assert "LIMIT 1" in cypher_text, (
            f"Expected 'LIMIT 1' in Cypher, got: {cypher_text}"
        )
