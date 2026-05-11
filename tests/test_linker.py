"""Tests for SemanticLinker — contract: specifications/08_semantic_linking/contract.md."""
from __future__ import annotations

from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from knowledge_garden.models.note import Chunk
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.linker import LinkPhase, LinkResult, SemanticLinker


def _make_chunk(note_id=None, embedding=None) -> Chunk:
    return Chunk(
        note_id=note_id or uuid4(),
        content="test content",
        index=0,
        embedding=embedding or [0.1] * 768,
    )


@pytest.fixture
def graph_store():
    store = AsyncMock(spec=GraphStore)
    store.get_all_chunks.return_value = []
    store.find_similar_chunks.return_value = []
    store.derive_related_to.return_value = 0
    return store


class TestLinkerLinkAll:
    """Contract: link_all() creates SIMILAR_TO edges for cross-note chunk pairs."""

    @pytest.mark.unit
    async def test_link_all_creates_similarity_edges(self, graph_store) -> None:
        """Contract: find_similar_chunks returns a cross-note match → create_similarity called."""
        note_1 = uuid4()
        note_2 = uuid4()
        chunk_a = _make_chunk(note_id=note_1)
        chunk_b = _make_chunk(note_id=note_2)

        graph_store.get_all_chunks.return_value = [chunk_a]
        graph_store.find_similar_chunks.return_value = [(chunk_b, 0.85)]

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        graph_store.create_similarity.assert_called_once_with(chunk_a.id, chunk_b.id, 0.85)
        assert result.similarity_edges_created == 1

    @pytest.mark.unit
    async def test_link_all_excludes_same_note(self, graph_store) -> None:
        """Contract: match from same note → create_similarity NOT called."""
        note_id = uuid4()
        chunk_a = _make_chunk(note_id=note_id)
        chunk_b = _make_chunk(note_id=note_id)

        graph_store.get_all_chunks.return_value = [chunk_a]
        graph_store.find_similar_chunks.return_value = [(chunk_b, 0.9)]

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        graph_store.create_similarity.assert_not_called()
        assert result.similarity_edges_created == 0

    @pytest.mark.unit
    async def test_link_all_no_matches(self, graph_store) -> None:
        """Contract: find_similar_chunks returns [] → create_similarity never called."""
        graph_store.get_all_chunks.return_value = [_make_chunk()]
        graph_store.find_similar_chunks.return_value = []

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        graph_store.create_similarity.assert_not_called()
        assert result.similarity_edges_created == 0

    @pytest.mark.unit
    async def test_link_all_respects_threshold(self, graph_store) -> None:
        """Contract: find_similar_chunks called with threshold from constructor."""
        graph_store.get_all_chunks.return_value = [_make_chunk()]

        linker = SemanticLinker(graph_store, threshold=0.85)
        await linker.link_all()

        graph_store.find_similar_chunks.assert_called_with(
            embedding=ANY, limit=ANY, threshold=0.85
        )

    @pytest.mark.unit
    async def test_link_all_respects_max_neighbors(self, graph_store) -> None:
        """Contract: find_similar_chunks called with limit=max_neighbors from constructor."""
        graph_store.get_all_chunks.return_value = [_make_chunk()]

        linker = SemanticLinker(graph_store, max_neighbors=5)
        await linker.link_all()

        graph_store.find_similar_chunks.assert_called_with(
            embedding=ANY, limit=5, threshold=ANY
        )

    @pytest.mark.unit
    async def test_link_all_idempotent(self, graph_store) -> None:
        """Contract: running link_all twice with same data succeeds both times (MERGE semantics)."""
        note_1 = uuid4()
        note_2 = uuid4()
        chunk_a = _make_chunk(note_id=note_1)
        chunk_b = _make_chunk(note_id=note_2)

        graph_store.get_all_chunks.return_value = [chunk_a]
        graph_store.find_similar_chunks.return_value = [(chunk_b, 0.85)]

        linker = SemanticLinker(graph_store)
        result1 = await linker.link_all()
        result2 = await linker.link_all()

        assert result1.chunks_processed == result2.chunks_processed
        assert result1.similarity_edges_created == result2.similarity_edges_created

    @pytest.mark.unit
    async def test_link_all_progress_callback(self, graph_store) -> None:
        """Contract: both LinkPhase.SIMILAR and LinkPhase.RELATED callbacks are emitted."""
        note_1 = uuid4()
        note_2 = uuid4()
        chunk_a = _make_chunk(note_id=note_1)
        chunk_b = _make_chunk(note_id=note_2)

        graph_store.get_all_chunks.return_value = [chunk_a]
        graph_store.find_similar_chunks.return_value = [(chunk_b, 0.8)]

        phases: list[LinkPhase] = []
        linker = SemanticLinker(graph_store)
        await linker.link_all(
            progress_callback=lambda phase, cur, tot, detail: phases.append(phase)
        )

        assert LinkPhase.SIMILAR in phases
        assert LinkPhase.RELATED in phases

    @pytest.mark.unit
    async def test_link_all_exception_treated_as_no_matches(self, graph_store) -> None:
        """Contract: find_similar_chunks raises exception → fail open, no edges created."""
        graph_store.get_all_chunks.return_value = [_make_chunk()]
        graph_store.find_similar_chunks.side_effect = RuntimeError("network error")

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        graph_store.create_similarity.assert_not_called()
        assert result.similarity_edges_created == 0

    @pytest.mark.unit
    async def test_link_all_zero_chunks(self, graph_store) -> None:
        """Contract: zero chunks in graph → chunks_processed=0, similarity_edges_created=0."""
        graph_store.get_all_chunks.return_value = []

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        assert result.chunks_processed == 0
        assert result.similarity_edges_created == 0


class TestLinkerDeriveNoteRelationships:
    """Contract: derive_note_relationships() calls derive_related_to on graph_store."""

    @pytest.mark.unit
    async def test_derive_calls_graph_store(self, graph_store) -> None:
        """Contract: derive_related_to called with the linker's threshold."""
        graph_store.derive_related_to.return_value = 3

        linker = SemanticLinker(graph_store, threshold=0.8)
        count = await linker.derive_note_relationships()

        graph_store.derive_related_to.assert_called_once_with(threshold=0.8)
        assert count == 3

    @pytest.mark.unit
    async def test_derive_progress_callback(self, graph_store) -> None:
        """Contract: LinkPhase.RELATED callback is emitted after derive_related_to."""
        graph_store.derive_related_to.return_value = 5

        phases: list[LinkPhase] = []
        linker = SemanticLinker(graph_store)
        await linker.derive_note_relationships(
            progress_callback=lambda phase, cur, tot, detail: phases.append(phase)
        )

        assert LinkPhase.RELATED in phases


class TestLinkResult:
    """Contract: LinkResult dataclass shape."""

    @pytest.mark.unit
    def test_link_result_shape(self) -> None:
        """Contract: LinkResult has all four required fields."""
        result = LinkResult(
            chunks_processed=10,
            similarity_edges_created=5,
            note_relationships_derived=3,
            duration_seconds=1.5,
        )
        assert result.chunks_processed == 10
        assert result.similarity_edges_created == 5
        assert result.note_relationships_derived == 3
        assert result.duration_seconds == 1.5

    @pytest.mark.unit
    async def test_link_all_result_shape(self, graph_store) -> None:
        """Contract: link_all() returns a LinkResult with all required fields."""
        graph_store.get_all_chunks.return_value = []
        graph_store.derive_related_to.return_value = 0

        linker = SemanticLinker(graph_store)
        result = await linker.link_all()

        assert isinstance(result, LinkResult)
        assert isinstance(result.chunks_processed, int)
        assert isinstance(result.similarity_edges_created, int)
        assert isinstance(result.note_relationships_derived, int)
        assert isinstance(result.duration_seconds, float)
