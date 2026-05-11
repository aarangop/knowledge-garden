from __future__ import annotations

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from knowledge_garden.services.graph_store import SearchResult as ServiceSearchResult

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


class ExportRequest(BaseModel):
    output_dir: str | None = None


class ExportResponse(BaseModel):
    notes_exported: int
    files_written: int
    output_dir: str


class SearchResult(BaseModel):
    note_id: str
    title: str
    source_vault: str
    original_path: str
    score: float
    snippet: str
    heading_context: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int


class StatsResponse(BaseModel):
    note_count: int
    chunk_count: int
    similarity_edge_count: int
    related_to_edge_count: int
    links_to_edge_count: int
    vault_names: list[str]


@router.post("/export")
async def export_vault(body: ExportRequest, request: Request) -> ExportResponse:
    from knowledge_garden.services.exporter import VaultExporter

    graph_store = request.app.state.graph_store
    output_dir = body.output_dir or getattr(request.app.state, "export_output_dir", "./output")
    exporter = VaultExporter(graph_store, output_dir)
    result = await exporter.export()
    return ExportResponse(
        notes_exported=result.notes_exported,
        files_written=result.files_written,
        output_dir=str(output_dir),
    )


@router.post("/link")
async def link_knowledge(request: Request) -> dict[str, object]:
    from knowledge_garden.services.linker import SemanticLinker

    graph_store = request.app.state.graph_store
    linker = SemanticLinker(graph_store)
    result = await linker.link_all()
    return {
        "chunks_processed": result.chunks_processed,
        "similarity_edges_created": result.similarity_edges_created,
        "note_relationships_derived": result.note_relationships_derived,
        "duration_seconds": result.duration_seconds,
    }


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


@router.get("/search")
async def search_notes(
    request: Request,
    q: str,
    limit: int = Query(default=10, ge=1, le=50),
    vault: str | None = Query(default=None),
) -> SearchResponse:
    """Semantic search over the knowledge graph."""
    embedder = request.app.state.embedder
    graph_store = request.app.state.graph_store

    vectors = await embedder.embed([q])
    vector: list[float] = vectors[0]

    service_results: list[ServiceSearchResult] = await graph_store.search_notes(
        query_embedding=vector,
        limit=limit,
        vault_filter=vault,
    )

    results = [
        SearchResult(
            note_id=sr.note_id,
            title=sr.title,
            source_vault=sr.source_vault,
            original_path=sr.original_path,
            score=sr.score,
            snippet=sr.snippet,
            heading_context=sr.heading_context,
        )
        for sr in service_results
    ]
    return SearchResponse(results=results, query=q, total=len(results))


@router.get("/stats")
async def get_graph_stats(request: Request) -> StatsResponse:
    """Return graph statistics."""
    graph_store = request.app.state.graph_store
    stats = await graph_store.get_stats()
    return StatsResponse(
        note_count=stats["note_count"],
        chunk_count=stats["chunk_count"],
        similarity_edge_count=stats["similarity_edge_count"],
        related_to_edge_count=stats["related_to_edge_count"],
        links_to_edge_count=stats["links_to_edge_count"],
        vault_names=stats["vault_names"],
    )
