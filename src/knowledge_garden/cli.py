from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from knowledge_garden.config import Config, VaultConfig
from knowledge_garden.models.note import Note
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.graph_store import GraphStore
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.pipeline import IngestPipeline, IngestResult

app = typer.Typer()


def _load_config(path: str = "config.yaml") -> Config:
    return Config.from_yaml(path)


def _make_embedder(config: Config) -> EmbeddingService:
    from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
    from knowledge_garden.services.together_embedder import TogetherAIEmbedder

    provider = config.embedding.provider
    if provider == "together":
        return TogetherAIEmbedder(config.together_ai, config.embedding)
    elif provider == "huggingface":
        if config.hugging_face is None:
            raise ValueError("hugging_face config required when provider is 'huggingface'")
        return HuggingFaceEmbedder(config.hugging_face, config.embedding)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")


def _make_graph_store(config: Config) -> Neo4jGraphStore:
    return Neo4jGraphStore(config.neo4j, config.embedding)


async def _run_ingest(
    vault_config: VaultConfig,
    embedder: EmbeddingService,
    graph_store: GraphStore,
    config: Config,
) -> IngestResult:
    from knowledge_garden.services.chunker import NoteChunker
    from knowledge_garden.services.parser import MarkdownParser

    await graph_store.initialize()
    try:
        pipeline = IngestPipeline(
            parser=MarkdownParser(),
            chunker=NoteChunker(config.chunking),
            embedder=embedder,
            graph_store=graph_store,
        )
        with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:
            task_id = progress.add_task("Ingesting notes...", total=None)

            def progress_callback(current: int, total: int, note_title: str) -> None:
                progress.update(task_id, description=f"[{current}/{total}] {note_title}")

            return await pipeline.run(vault_config, progress_callback=progress_callback)
    finally:
        await graph_store.close()


async def _run_notes(
    graph_store: GraphStore,
    *,
    vault_filter: str | None = None,
) -> list[Note]:
    await graph_store.initialize()
    try:
        notes = await graph_store.get_all_notes()
        if vault_filter:
            notes = [n for n in notes if n.vault == vault_filter]
        return notes
    finally:
        await graph_store.close()


async def _run_status(graph_store: GraphStore) -> list[Note]:
    await graph_store.initialize()
    try:
        return await graph_store.get_all_notes()
    finally:
        await graph_store.close()


@app.command()
def ingest(
    vault_name: str,
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        config = _load_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    vault_config = next((v for v in config.vaults if v.name == vault_name), None)
    if vault_config is None:
        typer.echo(f"Vault '{vault_name}' not found in configuration")
        raise typer.Exit(1) from None

    try:
        embedder = _make_embedder(config)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(config)
    result = asyncio.run(_run_ingest(vault_config, embedder, graph_store, config))

    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Notes parsed", str(result.notes_parsed))
    table.add_row("Chunks created", str(result.chunks_created))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    Console().print(table)


@app.command()
def notes(vault: str | None = typer.Option(None, "--vault")) -> None:
    try:
        config = _load_config()
    except FileNotFoundError:
        typer.echo("Config file not found: config.yaml")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(config)
    notes_list = asyncio.run(_run_notes(graph_store, vault_filter=vault))

    if not notes_list:
        typer.echo("No notes found")
        return

    table = Table()
    table.add_column("ID")
    table.add_column("Title")
    table.add_column("Vault")
    table.add_column("Links")
    for note in notes_list:
        table.add_row(
            str(note.id)[:8],
            note.title,
            note.vault,
            str(len(note.outgoing_links)),
        )
    Console().print(table)


@app.command()
def status() -> None:
    try:
        config = _load_config()
    except FileNotFoundError:
        typer.echo("Config file not found: config.yaml")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(config)
    all_notes = asyncio.run(_run_status(graph_store))

    if not all_notes:
        typer.echo("No data in graph")
        return

    vault_counts: dict[str, int] = {}
    for note in all_notes:
        vault_counts[note.vault] = vault_counts.get(note.vault, 0) + 1

    table = Table()
    table.add_column("Vault")
    table.add_column("Notes")
    for vault_name in sorted(vault_counts):
        table.add_row(vault_name, str(vault_counts[vault_name]))
    table.add_row("Total", str(len(all_notes)))
    Console().print(table)
