"""Tests for GET /api/v1/search and GET /api/v1/stats endpoints.

Contract: specifications/10_search_api/contract.md, sections 6, 7, and 8.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from knowledge_garden.api.routes import router as api_router
from knowledge_garden.models.note import Chunk, Note
from knowledge_garden.services.graph_store import GraphStore

# Import the service-layer SearchResult dataclass (does not exist yet — ImportError
# counts as the red-phase failure for tests that depend on it).
try:
    from knowledge_garden.services.graph_store import SearchResult as ServiceSearchResult
    _SEARCH_RESULT_AVAILABLE = True
except ImportError:
    ServiceSearchResult = None  # type: ignore[assignment, misc]
    _SEARCH_RESULT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_note(
    title: str = "Test Note",
    vault: str = "test_vault",
    original_path: str = "test.md",
    note_id: uuid.UUID | None = None,
) -> Note:
    """Factory: return a Note with specified fields."""
    kwargs: dict = dict(title=title, content="note content", vault=vault, original_path=original_path)
    if note_id is not None:
        kwargs["id"] = note_id
    return Note(**kwargs)


def _make_chunk(
    note_id: uuid.UUID,
    content: str = "chunk content",
    heading_context: str = "## Heading",
    index: int = 0,
) -> Chunk:
    """Factory: return a Chunk attached to note_id."""
    return Chunk(note_id=note_id, content=content, heading_context=heading_context, index=index)


def _make_service_search_result(
    note_id: str = "00000000-0000-0000-0000-000000000001",
    title: str = "Result Note",
    source_vault: str = "vault_a",
    original_path: str = "result.md",
    score: float = 0.92,
    snippet: str = "snippet text",
    heading_context: str = "## Section",
) -> "ServiceSearchResult":
    """Build a service-layer SearchResult (will raise if class not yet defined)."""
    return ServiceSearchResult(  # type: ignore[call-arg]
        note_id=note_id,
        title=title,
        source_vault=source_vault,
        original_path=original_path,
        score=score,
        snippet=snippet,
        heading_context=heading_context,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_search_graph_store():
    """AsyncMock of GraphStore with search_notes and get_stats pre-configured."""
    store = AsyncMock(spec=GraphStore)
    store.search_notes.return_value = []
    store.get_stats.return_value = {
        "note_count": 0,
        "chunk_count": 0,
        "similarity_edge_count": 0,
        "related_to_edge_count": 0,
        "links_to_edge_count": 0,
        "vault_names": [],
    }
    return store


@pytest.fixture
def mock_search_embedder():
    """AsyncMock embedder returning a single 768-dim vector."""
    embedder = AsyncMock()
    embedder.embed.return_value = [[0.1] * 768]
    return embedder


@pytest.fixture
def search_test_app(mock_search_graph_store, mock_search_embedder):
    """Minimal FastAPI app with mocked graph_store and embedder on app.state."""
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.graph_store = mock_search_graph_store
    app.state.embedder = mock_search_embedder
    return app


# ---------------------------------------------------------------------------
# TestSearchEndpoint
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    """Contract sections 7 — GET /api/v1/search endpoint."""

    @pytest.mark.unit
    async def test_search_returns_200(self, search_test_app, mock_search_graph_store):
        """Contract: valid q parameter → HTTP 200."""
        if not _SEARCH_RESULT_AVAILABLE:
            pytest.skip("ServiceSearchResult not yet defined (expected red-phase failure)")

        result = _make_service_search_result()
        mock_search_graph_store.search_notes.return_value = [result]

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello")

        assert response.status_code == 200

    @pytest.mark.unit
    async def test_search_response_schema(self, search_test_app, mock_search_graph_store):
        """Contract: response JSON has top-level keys results, query, total."""
        if not _SEARCH_RESULT_AVAILABLE:
            pytest.skip("ServiceSearchResult not yet defined (expected red-phase failure)")

        result = _make_service_search_result()
        mock_search_graph_store.search_notes.return_value = [result]

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello")

        body = response.json()
        assert "results" in body
        assert "query" in body
        assert "total" in body

    @pytest.mark.unit
    async def test_search_result_fields(self, search_test_app, mock_search_graph_store):
        """Contract: each item in results has note_id, title, source_vault, original_path,
        score, snippet, heading_context.
        """
        if not _SEARCH_RESULT_AVAILABLE:
            pytest.skip("ServiceSearchResult not yet defined (expected red-phase failure)")

        result = _make_service_search_result(
            note_id="aabbccdd-0000-0000-0000-000000000001",
            title="My Note",
            source_vault="vaultX",
            original_path="notes/my.md",
            score=0.88,
            snippet="a short snippet",
            heading_context="## Chapter 1",
        )
        mock_search_graph_store.search_notes.return_value = [result]

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello")

        body = response.json()
        assert response.status_code == 200
        assert len(body["results"]) == 1
        item = body["results"][0]
        for field in ("note_id", "title", "source_vault", "original_path", "score", "snippet", "heading_context"):
            assert field in item, f"Missing field '{field}' in search result"

    @pytest.mark.unit
    async def test_search_empty_results(self, search_test_app, mock_search_graph_store):
        """Contract: search_notes returns [] → results=[], total=0, HTTP 200."""
        mock_search_graph_store.search_notes.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello")

        assert response.status_code == 200
        body = response.json()
        assert body["results"] == []
        assert body["total"] == 0

    @pytest.mark.unit
    async def test_search_vault_filter_passed(self, search_test_app, mock_search_graph_store):
        """Contract: vault query param is forwarded to search_notes as vault_filter."""
        mock_search_graph_store.search_notes.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            await client.get("/api/v1/search?q=hello&vault=v1")

        mock_search_graph_store.search_notes.assert_called_once()
        call_kwargs = mock_search_graph_store.search_notes.call_args.kwargs
        assert call_kwargs.get("vault_filter") == "v1"

    @pytest.mark.unit
    async def test_search_limit_passed(self, search_test_app, mock_search_graph_store):
        """Contract: limit query param is forwarded to search_notes as limit."""
        mock_search_graph_store.search_notes.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            await client.get("/api/v1/search?q=hello&limit=5")

        mock_search_graph_store.search_notes.assert_called_once()
        call_kwargs = mock_search_graph_store.search_notes.call_args.kwargs
        assert call_kwargs.get("limit") == 5

    @pytest.mark.unit
    async def test_search_query_echoed(self, search_test_app, mock_search_graph_store):
        """Contract: response.query == the q parameter value."""
        mock_search_graph_store.search_notes.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=my+query")

        assert response.status_code == 200
        assert response.json()["query"] == "my query"

    @pytest.mark.unit
    async def test_search_total_matches_results_length(
        self, search_test_app, mock_search_graph_store
    ):
        """Contract: response total equals len(results)."""
        if not _SEARCH_RESULT_AVAILABLE:
            pytest.skip("ServiceSearchResult not yet defined (expected red-phase failure)")

        results = [
            _make_service_search_result(note_id=f"aabb{i:04d}-0000-0000-0000-000000000001")
            for i in range(3)
        ]
        mock_search_graph_store.search_notes.return_value = results

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello")

        body = response.json()
        assert body["total"] == 3
        assert len(body["results"]) == 3

    @pytest.mark.unit
    async def test_search_missing_q_returns_422(self, search_test_app):
        """Contract: GET /api/v1/search with no q parameter → HTTP 422."""
        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search")

        assert response.status_code == 422

    @pytest.mark.unit
    async def test_search_limit_zero_returns_422(self, search_test_app):
        """Contract: limit=0 violates ge=1 constraint → HTTP 422."""
        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello&limit=0")

        assert response.status_code == 422

    @pytest.mark.unit
    async def test_search_limit_above_max_returns_422(self, search_test_app):
        """Contract: limit=51 violates le=50 constraint → HTTP 422."""
        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/search?q=hello&limit=51")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# TestStatsEndpoint
# ---------------------------------------------------------------------------


class TestStatsEndpoint:
    """Contract section 8 — GET /api/v1/stats endpoint."""

    @pytest.mark.unit
    async def test_stats_returns_200(self, search_test_app, mock_search_graph_store):
        """Contract: get_stats returns valid dict → HTTP 200."""
        mock_search_graph_store.get_stats.return_value = {
            "note_count": 1,
            "chunk_count": 2,
            "similarity_edge_count": 3,
            "related_to_edge_count": 4,
            "links_to_edge_count": 5,
            "vault_names": ["v1"],
        }

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stats")

        assert response.status_code == 200

    @pytest.mark.unit
    async def test_stats_response_schema(self, search_test_app, mock_search_graph_store):
        """Contract: response JSON has note_count, chunk_count, similarity_edge_count,
        related_to_edge_count, links_to_edge_count, vault_names.
        """
        mock_search_graph_store.get_stats.return_value = {
            "note_count": 1,
            "chunk_count": 2,
            "similarity_edge_count": 3,
            "related_to_edge_count": 4,
            "links_to_edge_count": 5,
            "vault_names": ["v1"],
        }

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stats")

        body = response.json()
        for key in (
            "note_count",
            "chunk_count",
            "similarity_edge_count",
            "related_to_edge_count",
            "links_to_edge_count",
            "vault_names",
        ):
            assert key in body, f"Missing key '{key}' in stats response"

    @pytest.mark.unit
    async def test_stats_values_match_graph_store(
        self, search_test_app, mock_search_graph_store
    ):
        """Contract: all response fields exactly match what get_stats returns."""
        mock_search_graph_store.get_stats.return_value = {
            "note_count": 3,
            "chunk_count": 9,
            "similarity_edge_count": 15,
            "related_to_edge_count": 4,
            "links_to_edge_count": 2,
            "vault_names": ["v1", "v2"],
        }

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stats")

        body = response.json()
        assert body["note_count"] == 3
        assert body["chunk_count"] == 9
        assert body["similarity_edge_count"] == 15
        assert body["related_to_edge_count"] == 4
        assert body["links_to_edge_count"] == 2
        assert body["vault_names"] == ["v1", "v2"]

    @pytest.mark.unit
    async def test_stats_empty_graph(self, search_test_app, mock_search_graph_store):
        """Contract: empty graph → all counts 0, vault_names=[], HTTP 200."""
        mock_search_graph_store.get_stats.return_value = {
            "note_count": 0,
            "chunk_count": 0,
            "similarity_edge_count": 0,
            "related_to_edge_count": 0,
            "links_to_edge_count": 0,
            "vault_names": [],
        }

        async with AsyncClient(
            transport=ASGITransport(app=search_test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stats")

        assert response.status_code == 200
        body = response.json()
        assert body["note_count"] == 0
        assert body["chunk_count"] == 0
        assert body["similarity_edge_count"] == 0
        assert body["related_to_edge_count"] == 0
        assert body["links_to_edge_count"] == 0
        assert body["vault_names"] == []
