from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class NoteSummary(BaseModel):
    id: str
    title: str
    vault: str
    original_path: str
    outgoing_links: list[str]


class NotesListResponse(BaseModel):
    notes: list[NoteSummary]
    total: int


@router.get("/notes")
async def list_notes(request: Request) -> NotesListResponse:
    graph_store = request.app.state.graph_store
    notes = await graph_store.get_all_notes()
    summaries = [
        NoteSummary(
            id=str(note.id),
            title=note.title,
            vault=note.vault,
            original_path=note.original_path,
            outgoing_links=note.outgoing_links,
        )
        for note in notes
    ]
    return NotesListResponse(notes=summaries, total=len(summaries))
