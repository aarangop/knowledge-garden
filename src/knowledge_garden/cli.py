from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table

from knowledge_garden.config import AppSettings, BusinessConfig, VaultConfig
from knowledge_garden.models.note import Note
from knowledge_garden.services.embedder import EmbeddingService
from knowledge_garden.services.exporter import ExportResult
from knowledge_garden.services.graph_store import GraphStore, SearchResult
from knowledge_garden.services.linker import LinkPhase, LinkResult, SemanticLinker
from knowledge_garden.services.neo4j_store import Neo4jGraphStore
from knowledge_garden.services.pipeline import IngestPhase, IngestPipeline, IngestResult

app = typer.Typer()


def _load_app_settings() -> AppSettings:
    """Instantiate AppSettings from environment / .env file.

    Raises pydantic_settings.ValidationError if TOGETHER_API_KEY is absent.
    """
    return AppSettings()


def _load_business_config(path: str) -> BusinessConfig:
    """Load BusinessConfig from a YAML file.

    Raises FileNotFoundError if the file does not exist.
    Raises yaml.YAMLError for malformed YAML.
    Raises pydantic.ValidationError for schema violations.
    """
    return BusinessConfig.from_yaml(path)


def _make_embedder(settings: AppSettings, business: BusinessConfig) -> EmbeddingService:
    from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
    from knowledge_garden.services.together_embedder import TogetherAIEmbedder

    provider = business.embedding.provider
    if provider == "together":
        return TogetherAIEmbedder(settings.together_ai, business.embedding)
    elif provider == "huggingface":
        hf = settings.hugging_face
        if hf is None:
            raise ValueError("HF_API_TOKEN is required when embedding.provider is 'huggingface'")
        return HuggingFaceEmbedder(hf, business.embedding)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}")


def _make_graph_store(settings: AppSettings, business: BusinessConfig) -> Neo4jGraphStore:
    return Neo4jGraphStore(settings.neo4j, business.embedding)


async def _run_ingest(
    vault_config: VaultConfig,
    embedder: EmbeddingService,
    graph_store: GraphStore,
    business: BusinessConfig,
) -> IngestResult:
    from knowledge_garden.services.chunker import NoteChunker
    from knowledge_garden.services.parser import MarkdownParser

    await graph_store.initialize()
    try:
        pipeline = IngestPipeline(
            parser=MarkdownParser(),
            chunker=NoteChunker(business.chunking),
            embedder=embedder,
            graph_store=graph_store,
            embed_batch_size=business.embedding.batch_size,
            dedup_threshold=business.dedup.threshold,
        )
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ) as progress:
            chunking_task = progress.add_task(
                "Chunking notes...", total=None
            )
            dedup_task = progress.add_task(
                "Deduplicating...", total=None, visible=False
            )
            upsert_task = progress.add_task(
                "Upserting to graph...", total=None, visible=False
            )

            phase_task_map: dict[IngestPhase, TaskID] = {
                IngestPhase.CHUNKING: chunking_task,
                IngestPhase.DEDUP: dedup_task,
                IngestPhase.UPSERT: upsert_task,
            }
            phase_total_set: set[IngestPhase] = set()

            def progress_callback(
                phase: IngestPhase, current: int, total: int, detail: str
            ) -> None:
                task_id = phase_task_map[phase]
                if phase not in phase_total_set:
                    for p, tid in phase_task_map.items():
                        progress.update(tid, visible=(p == phase))
                    progress.update(task_id, total=total, visible=True)
                    phase_total_set.add(phase)
                progress.update(
                    task_id,
                    completed=current,
                    description=(
                        f"{phase.value.capitalize()}"
                        f" — {detail}"
                    ),
                )

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


async def _run_link(
    graph_store: GraphStore,
    threshold: float,
    max_neighbors: int,
) -> LinkResult:
    await graph_store.initialize()
    try:
        linker = SemanticLinker(graph_store, threshold=threshold, max_neighbors=max_neighbors)

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ) as progress:
            similar_task = progress.add_task("Linking chunks...", total=None)
            related_task = progress.add_task(
                "Deriving relationships...", total=None, visible=False
            )

            phase_task_map: dict[LinkPhase, TaskID] = {
                LinkPhase.SIMILAR: similar_task,
                LinkPhase.RELATED: related_task,
            }
            phase_total_set: set[LinkPhase] = set()

            def progress_callback(
                phase: LinkPhase, current: int, total: int, detail: str
            ) -> None:
                task_id = phase_task_map[phase]
                if phase not in phase_total_set:
                    for p, tid in phase_task_map.items():
                        progress.update(tid, visible=(p == phase))
                    progress.update(task_id, total=total, visible=True)
                    phase_total_set.add(phase)
                progress.update(
                    task_id,
                    completed=current,
                    description=f"{phase.value.capitalize()} — {detail}",
                )

            return await linker.link_all(progress_callback=progress_callback)
    finally:
        await graph_store.close()


async def _run_unlink(graph_store: GraphStore) -> dict[str, int]:
    await graph_store.initialize()
    try:
        return await graph_store.clear_semantic_edges()
    finally:
        await graph_store.close()


async def _run_export(
    graph_store: GraphStore,
    output_dir: str,
) -> ExportResult:
    from knowledge_garden.services.exporter import ExportPhase, VaultExporter

    await graph_store.initialize()
    try:
        exporter = VaultExporter(graph_store, output_dir)
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        ) as progress:
            writing_task = progress.add_task("Exporting notes...", total=None)

            def progress_callback(
                phase: ExportPhase, current: int, total: int, detail: str
            ) -> None:
                if phase == ExportPhase.WRITING:
                    progress.update(
                        writing_task,
                        total=total,
                        completed=current,
                        description=f"Writing — {detail}",
                    )

            return await exporter.export(progress_callback=progress_callback)
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
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    vault_config = next((v for v in business.vaults if v.name == vault_name), None)
    if vault_config is None:
        typer.echo(f"Vault '{vault_name}' not found in configuration")
        raise typer.Exit(1) from None

    try:
        embedder = _make_embedder(settings, business)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
    result = asyncio.run(_run_ingest(vault_config, embedder, graph_store, business))

    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Notes parsed", str(result.notes_parsed))
    table.add_row("Chunks created", str(result.chunks_created))
    table.add_row("Chunks skipped (dedup)", str(result.chunks_skipped))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    Console().print(table)


@app.command()
def notes(
    vault: str | None = typer.Option(None, "--vault"),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
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
def link(
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
    result = asyncio.run(
        _run_link(
            graph_store,
            threshold=business.linking.threshold,
            max_neighbors=business.linking.max_neighbors,
        )
    )

    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Chunks processed", str(result.chunks_processed))
    table.add_row("Similarity edges", str(result.similarity_edges_created))
    table.add_row("Note relationships", str(result.note_relationships_derived))
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    Console().print(table)


@app.command()
def unlink(
    config_path: str = typer.Option("config.yaml", "--config"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Delete all SIMILAR_TO and RELATED_TO edges so `link` can be re-run from scratch.

    Notes, chunks, embeddings, and explicit LINKS_TO (wikilinks) are preserved.
    """
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    if not yes:
        confirm = typer.confirm(
            "Delete all SIMILAR_TO and RELATED_TO edges? Notes and wikilinks are preserved.",
            default=False,
        )
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit(0)

    graph_store = _make_graph_store(settings, business)
    counts = asyncio.run(_run_unlink(graph_store))

    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("SIMILAR_TO edges deleted", str(counts["similarity_edges_deleted"]))
    table.add_row("RELATED_TO edges deleted", str(counts["related_to_edges_deleted"]))
    Console().print(table)


@app.command()
def export(
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
    result = asyncio.run(_run_export(graph_store, business.export.output_dir))

    table = Table()
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Notes exported", str(result.notes_exported))
    table.add_row("Files written", str(result.files_written))
    table.add_row("Output dir", business.export.output_dir)
    table.add_row("Duration", f"{result.duration_seconds:.2f}s")
    Console().print(table)


async def _run_search(
    embedder: EmbeddingService,
    graph_store: GraphStore,
    query: str,
    limit: int,
    threshold: float,
    vault: str | None,
) -> list[SearchResult]:
    """Embed query, search for similar notes via graph_store.search_notes.

    Closes both graph_store and embedder in the finally block.
    """
    await graph_store.initialize()
    try:
        vectors = await embedder.embed([query])
        vector = vectors[0]
        return await graph_store.search_notes(
            query_embedding=vector,
            limit=limit,
            vault_filter=vault,
        )
    finally:
        await embedder.close()
        await graph_store.close()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    limit: int | None = typer.Option(
        None, "--limit", "-n", help="Maximum results (default: config search_limit)"
    ),
    threshold: float = typer.Option(
        0.7, "--threshold", help="Minimum similarity score (reserved, not yet applied)"
    ),
    vault: str | None = typer.Option(None, "--vault", help="Filter by source vault name"),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    effective_limit = limit if limit is not None else business.search.search_limit

    try:
        embedder = _make_embedder(settings, business)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
    results = asyncio.run(
        _run_search(embedder, graph_store, query, effective_limit, threshold, vault)
    )

    if not results:
        typer.echo("No results found.")
        return

    table = Table()
    table.add_column("Score")
    table.add_column("Note Title")
    table.add_column("Vault")
    table.add_column("Heading")
    table.add_column("Snippet")
    for result in results:
        table.add_row(
            f"{result.score:.4f}",
            result.title,
            result.source_vault,
            result.heading_context,
            result.snippet[:80],
        )
    Console().print(table)


@app.command()
def status(
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
    try:
        settings = _load_app_settings()
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from None

    try:
        business = _load_business_config(config_path)
    except FileNotFoundError:
        typer.echo(f"Config file not found: {config_path}")
        raise typer.Exit(1) from None

    graph_store = _make_graph_store(settings, business)
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
