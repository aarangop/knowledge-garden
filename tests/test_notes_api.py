"""Tests for GET /api/v1/notes endpoint — contract: specifications/02_ingestion/contract.md,
section notes listing.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from knowledge_garden.api.routes import router as api_router
from knowledge_garden.models.note import Note


@pytest.fixture
def test_app(mock_embedder, mock_graph_store):
    """Minimal FastAPI app with the API router and mocked services on app.state."""
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    app.state.embedder = mock_embedder
    app.state.graph_store = mock_graph_store
    return app


class TestNotesListEndpoint:
    """Contract: GET /api/v1/notes returns a list of note summaries from the graph store."""

    @pytest.mark.unit
    async def test_list_notes_empty(self, test_app, mock_graph_store):
        """Contract: when graph_store.get_all_notes() returns [], response is 200 with notes=[]
        and total=0.
        """
        mock_graph_store.get_all_notes.return_value = []

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/notes")

        assert response.status_code == 200
        body = response.json()
        assert body["notes"] == []
        assert body["total"] == 0

    @pytest.mark.unit
    async def test_list_notes_returns_correct_count(self, test_app, mock_graph_store):
        """Contract: when graph_store.get_all_notes() returns 3 Notes, total==3 and
        len(notes)==3.
        """
        notes = [
            Note(
                title=f"Note {i}", content="body",
                vault="test_vault", original_path=f"note_{i}.md",
            )
            for i in range(3)
        ]
        mock_graph_store.get_all_notes.return_value = notes

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/notes")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert len(body["notes"]) == 3

    @pytest.mark.unit
    async def test_list_notes_schema(self, test_app, mock_graph_store):
        """Contract: each note object in the response has keys id, title, vault, original_path,
        outgoing_links.
        """
        note = Note(
            title="Schema Note", content="body", vault="test_vault", original_path="schema.md"
        )
        mock_graph_store.get_all_notes.return_value = [note]

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/notes")

        assert response.status_code == 200
        note_obj = response.json()["notes"][0]
        for key in ("id", "title", "vault", "original_path", "outgoing_links"):
            assert key in note_obj, f"Missing key '{key}' in note summary"

    @pytest.mark.unit
    async def test_list_notes_id_is_string(self, test_app, mock_graph_store):
        """Contract: Note.id (UUID) is serialized as a string in the response."""
        note = Note(
            title="UUID Note", content="body", vault="test_vault", original_path="uuid.md"
        )
        mock_graph_store.get_all_notes.return_value = [note]

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/notes")

        assert response.status_code == 200
        note_id = response.json()["notes"][0]["id"]
        assert isinstance(note_id, str)
        assert str(note.id) == note_id

    @pytest.mark.unit
    async def test_list_notes_outgoing_links(self, test_app, mock_graph_store):
        """Contract: outgoing_links on the Note are preserved verbatim in the response."""
        note = Note(
            title="Links Note",
            content="body",
            vault="test_vault",
            original_path="links.md",
            outgoing_links=["A", "B"],
        )
        mock_graph_store.get_all_notes.return_value = [note]

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/notes")

        assert response.status_code == 200
        assert response.json()["notes"][0]["outgoing_links"] == ["A", "B"]


class TestExportEndpoint:
    """Contract section 6 — POST /api/v1/export endpoint."""

    @pytest.mark.unit
    async def test_export_endpoint_returns_200(self, test_app, mock_graph_store, tmp_path):
        """Contract: POST /api/v1/export with empty body returns HTTP 200."""
        mock_graph_store.get_all_notes.return_value = []
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        # Point the export output to a temporary directory so no real path is needed
        test_app.state.export_output_dir = str(tmp_path)

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/export", json={})

        assert response.status_code == 200

    @pytest.mark.unit
    async def test_export_endpoint_response_schema(
        self, test_app, mock_graph_store, tmp_path
    ):
        """Contract: response JSON contains notes_exported, files_written, output_dir."""
        mock_graph_store.get_all_notes.return_value = []
        mock_graph_store.get_note_relationships_with_scores.return_value = {}
        test_app.state.export_output_dir = str(tmp_path)

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/export", json={})

        body = response.json()
        for key in ("notes_exported", "files_written", "output_dir"):
            assert key in body, f"Missing key '{key}' in export response"

    @pytest.mark.unit
    async def test_export_endpoint_custom_output_dir(
        self, test_app, mock_graph_store, tmp_path
    ):
        """Contract: body output_dir is reflected back in the response output_dir field."""
        custom_dir = str(tmp_path / "custom_output")
        mock_graph_store.get_all_notes.return_value = []
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/export", json={"output_dir": custom_dir})

        body = response.json()
        assert body["output_dir"] == custom_dir


class TestLinkEndpoint:
    """Contract: POST /api/v1/link triggers linking and returns stats."""

    @pytest.mark.unit
    async def test_link_endpoint_returns_200(self, test_app, mock_graph_store) -> None:
        """Contract: POST /api/v1/link returns HTTP 200."""
        mock_graph_store.get_all_chunks.return_value = []
        mock_graph_store.derive_related_to.return_value = 0

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/link")

        assert response.status_code == 200

    @pytest.mark.unit
    async def test_link_endpoint_response_schema(self, test_app, mock_graph_store) -> None:
        """Contract: response contains chunks_processed, similarity_edges_created,
        note_relationships_derived, duration_seconds."""
        mock_graph_store.get_all_chunks.return_value = []
        mock_graph_store.derive_related_to.return_value = 0

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/link")

        body = response.json()
        for key in (
            "chunks_processed",
            "similarity_edges_created",
            "note_relationships_derived",
            "duration_seconds",
        ):
            assert key in body, f"Missing key '{key}' in link response"
