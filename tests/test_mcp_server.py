"""Tests for the MCP server tools — contract: specifications/12_mcp_server/contract.md.

All tests are unit tests that call the tool functions directly (not via the MCP
protocol). They inject a mock Context whose `request_context.lifespan_context`
attribute holds an `AppState` instance — matching the shape FastMCP exposes at
request time.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from knowledge_garden.models.note import Chunk, Note
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore


# ---------------------------------------------------------------------------
# Fixtures (spec 12 §7)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_graph_store() -> AsyncMock:
    """AsyncMock(spec=GraphStore) with sensible defaults."""
    store = AsyncMock(spec=GraphStore)
    store.find_similar_chunks = AsyncMock(return_value=[])
    store.get_note_by_id = AsyncMock(return_value=None)
    store.get_note_by_title = AsyncMock(return_value=None)
    store.get_all_notes = AsyncMock(return_value=[])
    store.get_stats = AsyncMock(
        return_value={
            "note_count": 0,
            "chunk_count": 0,
            "similarity_edge_count": 0,
            "related_to_edge_count": 0,
            "links_to_edge_count": 0,
            "vault_names": [],
        }
    )
    return store


@pytest.fixture
def mock_embedder() -> AsyncMock:
    """AsyncMock(spec=EmbeddingService) whose embed() returns one 768-dim vector."""
    embedder = AsyncMock(spec=EmbeddingService)
    embedder.embed = AsyncMock(return_value=[[0.1] * 768])
    return embedder


@pytest.fixture
def mock_state(mock_graph_store: AsyncMock, mock_embedder: AsyncMock):
    """AppState instance wired with the mock store and embedder."""
    from knowledge_garden.mcp_server import AppState

    return AppState(graph_store=mock_graph_store, embedder=mock_embedder)


@pytest.fixture
def mock_ctx(mock_state) -> MagicMock:
    """MagicMock Context whose request_context.lifespan_context is mock_state."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = mock_state
    return ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    note_id: uuid.UUID,
    content: str = "chunk body",
    heading_context: str = "## Section",
    index: int = 0,
) -> Chunk:
    return Chunk(
        note_id=note_id,
        content=content,
        heading_context=heading_context,
        index=index,
        embedding=[0.1] * 768,
    )


def _make_note(
    note_id: uuid.UUID | None = None,
    title: str = "A Note",
    vault: str = "vault_a",
    original_path: str = "a.md",
    content: str = "note content",
) -> Note:
    kwargs: dict = dict(
        title=title, content=content, vault=vault, original_path=original_path
    )
    if note_id is not None:
        kwargs["id"] = note_id
    return Note(**kwargs)


# ---------------------------------------------------------------------------
# search_notes tool tests (spec 12 §7)
# ---------------------------------------------------------------------------


class TestSearchNotesTool:
    """Spec 12 §7 — search_notes tool unit tests."""

    @pytest.mark.unit
    async def test_search_notes_returns_json_string(
        self, mock_ctx, mock_graph_store, mock_embedder
    ):
        """Spec 12 §7: returns a JSON array; element has the documented keys."""
        from knowledge_garden.mcp_server import search_notes

        note_id = uuid.uuid4()
        chunk = _make_chunk(note_id=note_id, content="ML stuff", heading_context="# Intro")
        note = _make_note(
            note_id=note_id,
            title="ML",
            vault="vault_a",
            original_path="ml.md",
            content="full note content",
        )
        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[(chunk, 0.85)])
        mock_graph_store.get_note_by_id = AsyncMock(return_value=note)

        result = await search_notes("ML concepts", ctx=mock_ctx)

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        entry = parsed[0]
        for key in (
            "note_title",
            "source_vault",
            "chunk_content",
            "heading_context",
            "score",
            "original_path",
        ):
            assert key in entry, f"Missing key '{key}' in result entry: {entry}"
        # Internal UUID must not be exposed.
        assert "note_id" not in entry

    @pytest.mark.unit
    async def test_search_notes_empty_results(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: find_similar_chunks returns [] → return value is '[]'."""
        from knowledge_garden.mcp_server import search_notes

        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[])

        result = await search_notes("anything", ctx=mock_ctx)

        assert result == "[]"

    @pytest.mark.unit
    async def test_search_notes_vault_filter(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: vault='vault_a' → only the chunk whose note is in vault_a is returned."""
        from knowledge_garden.mcp_server import search_notes

        note_a_id = uuid.uuid4()
        note_b_id = uuid.uuid4()
        chunk_a = _make_chunk(note_id=note_a_id, content="A chunk")
        chunk_b = _make_chunk(note_id=note_b_id, content="B chunk")
        note_a = _make_note(note_id=note_a_id, vault="vault_a")
        note_b = _make_note(note_id=note_b_id, vault="vault_b")

        mock_graph_store.find_similar_chunks = AsyncMock(
            return_value=[(chunk_a, 0.9), (chunk_b, 0.85)]
        )

        async def get_note(nid):
            if str(nid) == str(note_a_id):
                return note_a
            return note_b

        mock_graph_store.get_note_by_id = AsyncMock(side_effect=get_note)

        result = await search_notes("q", vault="vault_a", ctx=mock_ctx)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["source_vault"] == "vault_a"

    @pytest.mark.unit
    async def test_search_notes_limit_passed_to_store(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: limit=5 → find_similar_chunks called with limit=5."""
        from knowledge_garden.mcp_server import search_notes

        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[])

        await search_notes("q", limit=5, ctx=mock_ctx)

        mock_graph_store.find_similar_chunks.assert_called_once()
        call_kwargs = mock_graph_store.find_similar_chunks.call_args.kwargs
        assert call_kwargs.get("limit") == 5

    @pytest.mark.unit
    async def test_search_notes_limit_clamped_max(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: limit=200 → clamped to 50 when forwarded to the store."""
        from knowledge_garden.mcp_server import search_notes

        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[])

        await search_notes("q", limit=200, ctx=mock_ctx)

        call_kwargs = mock_graph_store.find_similar_chunks.call_args.kwargs
        assert call_kwargs.get("limit") == 50

    @pytest.mark.unit
    async def test_search_notes_limit_clamped_min(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: limit=0 → clamped to 1 when forwarded to the store."""
        from knowledge_garden.mcp_server import search_notes

        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[])

        await search_notes("q", limit=0, ctx=mock_ctx)

        call_kwargs = mock_graph_store.find_similar_chunks.call_args.kwargs
        assert call_kwargs.get("limit") == 1

    @pytest.mark.unit
    async def test_search_notes_threshold_passed_to_store(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: threshold=0.9 → find_similar_chunks called with threshold=0.9."""
        from knowledge_garden.mcp_server import search_notes

        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[])

        await search_notes("q", threshold=0.9, ctx=mock_ctx)

        call_kwargs = mock_graph_store.find_similar_chunks.call_args.kwargs
        assert call_kwargs.get("threshold") == 0.9

    @pytest.mark.unit
    async def test_search_notes_skips_note_not_found(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: get_note_by_id returns None → chunk skipped → result is '[]'."""
        from knowledge_garden.mcp_server import search_notes

        note_id = uuid.uuid4()
        chunk = _make_chunk(note_id=note_id)
        mock_graph_store.find_similar_chunks = AsyncMock(return_value=[(chunk, 0.85)])
        mock_graph_store.get_note_by_id = AsyncMock(return_value=None)

        result = await search_notes("q", ctx=mock_ctx)

        assert result == "[]"


# ---------------------------------------------------------------------------
# get_note tool tests (spec 12 §7)
# ---------------------------------------------------------------------------


class TestGetNoteTool:
    """Spec 12 §7 — get_note tool unit tests."""

    @pytest.mark.unit
    async def test_get_note_found(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: get_note_by_title returns Note with content='Hello world' → returns 'Hello world'."""
        from knowledge_garden.mcp_server import get_note

        note = _make_note(title="Greeting", content="Hello world")
        mock_graph_store.get_note_by_title = AsyncMock(return_value=note)

        result = await get_note("Greeting", ctx=mock_ctx)

        assert result == "Hello world"

    @pytest.mark.unit
    async def test_get_note_not_found(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: get_note_by_title returns None → return value starts with 'Note not found:'."""
        from knowledge_garden.mcp_server import get_note

        mock_graph_store.get_note_by_title = AsyncMock(return_value=None)

        result = await get_note("missing", ctx=mock_ctx)

        assert result.startswith("Note not found:")


# ---------------------------------------------------------------------------
# list_vaults tool tests (spec 12 §7)
# ---------------------------------------------------------------------------


class TestListVaultsTool:
    """Spec 12 §7 — list_vaults tool unit tests."""

    @pytest.mark.unit
    async def test_list_vaults_returns_json(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: 3 notes (2 from v1, 1 from v2) → two-element array with correct counts."""
        from knowledge_garden.mcp_server import list_vaults

        notes = [
            _make_note(vault="v1", original_path="v1/a.md"),
            _make_note(vault="v1", original_path="v1/b.md"),
            _make_note(vault="v2", original_path="v2/c.md"),
        ]
        mock_graph_store.get_all_notes = AsyncMock(return_value=notes)

        result = await list_vaults(ctx=mock_ctx)

        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        by_vault = {entry["vault"]: entry["note_count"] for entry in parsed}
        assert by_vault == {"v1": 2, "v2": 1}

    @pytest.mark.unit
    async def test_list_vaults_empty_graph(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: get_all_notes returns [] → return value is '[]'."""
        from knowledge_garden.mcp_server import list_vaults

        mock_graph_store.get_all_notes = AsyncMock(return_value=[])

        result = await list_vaults(ctx=mock_ctx)

        assert result == "[]"


# ---------------------------------------------------------------------------
# get_graph_stats tool tests (spec 12 §7)
# ---------------------------------------------------------------------------


class TestGetGraphStatsTool:
    """Spec 12 §7 — get_graph_stats tool unit tests."""

    @pytest.mark.unit
    async def test_get_graph_stats_returns_json(self, mock_ctx, mock_graph_store):
        """Spec 12 §7: get_stats returns the canonical six-key dict → JSON dict with same keys."""
        from knowledge_garden.mcp_server import get_graph_stats

        stats = {
            "note_count": 5,
            "chunk_count": 20,
            "similarity_edge_count": 15,
            "related_to_edge_count": 3,
            "links_to_edge_count": 7,
            "vault_names": ["v1"],
        }
        mock_graph_store.get_stats = AsyncMock(return_value=stats)

        result = await get_graph_stats(ctx=mock_ctx)

        parsed = json.loads(result)
        assert isinstance(parsed, dict)
        assert parsed == stats
