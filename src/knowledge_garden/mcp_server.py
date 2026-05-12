"""Knowledge Garden MCP server.

Exposes Neo4j-backed semantic search and graph inspection as MCP tools so that
MCP clients (e.g. Claude Desktop) can query the knowledge graph directly.

Contract: specifications/12_mcp_server/contract.md.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from knowledge_garden.config import AppSettings, BusinessConfig
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.together_embedder import TogetherAIEmbedder

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Long-lived services shared across MCP tool invocations."""

    graph_store: GraphStore
    embedder: EmbeddingService


@asynccontextmanager
async def kg_lifespan(server: FastMCP) -> AsyncIterator[AppState]:
    """Initialise Neo4j and embedder on startup; close on shutdown.

    Loads `config.yaml` so the server embeds queries with the same model used
    during ingestion. Without this, dim/model mismatches silently break
    semantic search.
    """
    settings = AppSettings()
    business = BusinessConfig.from_yaml("config.yaml")
    embedding_config = business.embedding

    graph_store = Neo4jGraphStore(settings.neo4j, embedding_config)
    await graph_store.initialize()

    embedder: EmbeddingService
    provider = embedding_config.provider
    if provider == "huggingface":
        hf = settings.hugging_face
        if hf is None:
            raise ValueError(
                "HF_API_TOKEN is required when embedding.provider is 'huggingface'"
            )
        embedder = HuggingFaceEmbedder(hf, embedding_config)
    elif provider == "together":
        embedder = TogetherAIEmbedder(settings.together_ai, embedding_config)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")

    try:
        yield AppState(graph_store=graph_store, embedder=embedder)
    finally:
        await embedder.close()
        await graph_store.close()


mcp = FastMCP("Knowledge Garden", lifespan=kg_lifespan)


# Type alias for the Context shape FastMCP injects into our tools.
KGContext = Context[ServerSession, AppState, object]


@mcp.tool()
async def search_notes(
    query: str,
    limit: int = 10,
    threshold: float = 0.7,
    vault: str | None = None,
    ctx: KGContext = ...,  # type: ignore[assignment]
) -> str:
    """Search the knowledge graph for notes semantically related to a query.

    Args:
        query: The natural-language search query.
        limit: Maximum number of results to return (1-50, default 10).
        threshold: Minimum cosine similarity score for a result to be included
                   (0.0-1.0, default 0.7).
        vault: If provided, restrict results to notes from this vault name.

    Returns:
        A JSON-encoded array of objects. Each object has the fields:
            note_title (str), source_vault (str), chunk_content (str),
            heading_context (str), score (float), original_path (str).
        Returns "[]" if no results match.
    """
    state: AppState = ctx.request_context.lifespan_context

    clamped_limit = max(1, min(limit, 50))

    vectors = await state.embedder.embed([query])
    query_vector = vectors[0]

    pairs = await state.graph_store.find_similar_chunks(
        embedding=query_vector,
        limit=clamped_limit,
        threshold=threshold,
    )

    results: list[dict[str, object]] = []
    for chunk, score in pairs:
        note = await state.graph_store.get_note_by_id(chunk.note_id)
        if note is None:
            continue
        if vault is not None and note.vault != vault:
            continue
        results.append(
            {
                "note_title": note.title,
                "source_vault": note.vault,
                "chunk_content": chunk.content,
                "heading_context": chunk.heading_context,
                "score": score,
                "original_path": note.original_path,
            }
        )

    return json.dumps(results)


@mcp.tool()
async def get_note(
    title: str,
    ctx: KGContext = ...,  # type: ignore[assignment]
) -> str:
    """Retrieve the full markdown content of a note by title.

    Args:
        title: The note title to look up (case-insensitive).

    Returns:
        The full markdown content of the note if found.
        A plain-text error message beginning with "Note not found:" if no
        note matches the given title.
    """
    state: AppState = ctx.request_context.lifespan_context

    note = await state.graph_store.get_note_by_title(title)
    if note is None:
        return f"Note not found: {title!r}"
    return note.content


@mcp.tool()
async def list_vaults(ctx: KGContext = ...) -> str:  # type: ignore[assignment]
    """List all ingested vaults and their note counts.

    Returns:
        A JSON-encoded array of objects, each with fields:
            vault (str): vault name.
            note_count (int): number of notes from that vault.
        Returns "[]" if no notes have been ingested.
    """
    state: AppState = ctx.request_context.lifespan_context

    notes = await state.graph_store.get_all_notes()

    counts: dict[str, int] = {}
    for note in notes:
        counts[note.vault] = counts.get(note.vault, 0) + 1

    payload = [{"vault": vault, "note_count": count} for vault, count in counts.items()]
    return json.dumps(payload)


@mcp.tool()
async def get_graph_stats(ctx: KGContext = ...) -> str:  # type: ignore[assignment]
    """Get high-level statistics about the knowledge graph.

    Returns:
        A JSON-encoded object with fields:
            note_count (int): total Note nodes.
            chunk_count (int): total Chunk nodes.
            similarity_edge_count (int): total SIMILAR_TO edges.
            related_to_edge_count (int): total RELATED_TO edges.
            links_to_edge_count (int): total LINKS_TO edges.
            vault_names (list[str]): distinct vault names.
    """
    state: AppState = ctx.request_context.lifespan_context

    stats = await state.graph_store.get_stats()
    return json.dumps(stats)


def main() -> None:
    """Entry point for the kg-mcp script."""
    mcp.run()
