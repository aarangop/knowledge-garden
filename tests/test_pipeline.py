"""Tests for IngestPipeline service — contract: specifications/03_cli/contract.md, section 2."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from knowledge_garden.config import ChunkingConfig, VaultConfig
from knowledge_garden.models.note import Chunk, Note
from knowledge_garden.services.chunker import NoteChunker
from knowledge_garden.services.parser import MarkdownParser
from knowledge_garden.services.pipeline import IngestPipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_note(title: str = "Note A") -> Note:
    """Return a Note with real content sufficient to survive min_chunk_size filtering."""
    return Note(
        title=title,
        content="## Section\n\n" + "word " * 50,
        vault="test_vault",
        original_path=f"{title}.md",
    )


def make_chunk(note: Note, index: int = 0) -> Chunk:
    """Return a Chunk belonging to the given Note."""
    return Chunk(note_id=note.id, content="Chunk content.", index=index)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_chunking_config() -> ChunkingConfig:
    """ChunkingConfig with generous limits so real content produces chunks."""
    return ChunkingConfig(max_chunk_size=1000, min_chunk_size=10)


@pytest.fixture
def mock_parser() -> MagicMock:
    """MarkdownParser whose parse_vault is controlled per test."""
    return MagicMock(spec=MarkdownParser)


@pytest.fixture
def mock_chunker() -> MagicMock:
    """NoteChunker whose chunk_note is controlled per test."""
    return MagicMock(spec=NoteChunker)


@pytest.fixture
def sample_vault_config() -> VaultConfig:
    """A VaultConfig with a fixed name and path (does not need to exist on disk)."""
    return VaultConfig(name="test_vault", path="/tmp/test_vault")


@pytest.fixture
def pipeline(
    mock_parser: MagicMock,
    mock_chunker: MagicMock,
    mock_embedder: AsyncMock,
    mock_graph_store: AsyncMock,
) -> IngestPipeline:
    """IngestPipeline with all dependencies mocked (mock_chunker version)."""
    return IngestPipeline(
        parser=mock_parser,
        chunker=mock_chunker,
        embedder=mock_embedder,
        graph_store=mock_graph_store,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIngestPipelineResult:
    """Contract section 2.3 — result shape and basic return value."""

    @pytest.mark.unit
    async def test_pipeline_result_is_ingest_result(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: run() returns an instance of IngestResult."""
        from knowledge_garden.services.pipeline import IngestResult

        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]

        result = await pipeline.run(sample_vault_config)

        assert isinstance(result, IngestResult)

    @pytest.mark.unit
    async def test_pipeline_result_duration_non_negative(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: result.duration_seconds >= 0 for any run."""
        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]

        result = await pipeline.run(sample_vault_config)

        assert result.duration_seconds >= 0


class TestIngestPipelineEmptyVault:
    """Contract section 2.3 — empty vault behaviour."""

    @pytest.mark.unit
    async def test_pipeline_empty_vault(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: parse_vault returns [] → notes_parsed==0, chunks_created==0,
        embed not called, upsert_note not called.
        """
        mock_parser.parse_vault.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 0
        assert result.chunks_created == 0
        mock_embedder.embed.assert_not_called()
        mock_graph_store.upsert_note.assert_not_called()


class TestIngestPipelineSingleNote:
    """Contract section 2.3 — single-note scenarios."""

    @pytest.mark.unit
    async def test_pipeline_single_note_no_chunks(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 1 note, chunk_note returns [] → notes_parsed==1, chunks_created==0,
        embed not called, upsert_note called once, upsert_chunk not called.
        """
        note = make_note("Alpha")
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 1
        assert result.chunks_created == 0
        mock_embedder.embed.assert_not_called()
        mock_graph_store.upsert_note.assert_called_once()
        mock_graph_store.upsert_chunk.assert_not_called()

    @pytest.mark.unit
    async def test_pipeline_single_note_with_chunks(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 1 note, chunk_note returns 2 chunks, embed returns 2 vectors →
        notes_parsed==1, chunks_created==2, embed called once, upsert_chunk called twice.
        """
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        mock_embedder.embed.return_value = [[0.1] * 768, [0.2] * 768]

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 1
        assert result.chunks_created == 2
        mock_embedder.embed.assert_called_once()
        embed_texts = mock_embedder.embed.call_args[0][0]
        assert len(embed_texts) == 2
        mock_graph_store.upsert_note.assert_called_once()
        assert mock_graph_store.upsert_chunk.call_count == 2


class TestIngestPipelineMultipleNotes:
    """Contract section 2.3 — multiple-note scenarios."""

    @pytest.mark.unit
    async def test_pipeline_multiple_notes(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 3 notes, each producing 1 chunk → notes_parsed==3, chunks_created==3,
        upsert_note called 3 times, upsert_chunk called 3 times.
        """
        notes = [make_note(f"Note{i}") for i in range(3)]
        chunks = [make_chunk(note, index=0) for note in notes]
        mock_parser.parse_vault.return_value = notes
        mock_chunker.chunk_note.side_effect = [[c] for c in chunks]
        mock_embedder.embed.return_value = [[0.1] * 768] * 3

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 3
        assert result.chunks_created == 3
        assert mock_graph_store.upsert_note.call_count == 3
        assert mock_graph_store.upsert_chunk.call_count == 3

    @pytest.mark.unit
    async def test_pipeline_embed_called_once_for_all_chunks(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 2 notes each producing 3 chunks → embed called exactly once
        with a list of 6 texts.
        """
        notes = [make_note("A"), make_note("B")]
        mock_parser.parse_vault.return_value = notes

        def side_effect(note: Note) -> list[Chunk]:
            return [make_chunk(note, index=i) for i in range(3)]

        mock_chunker.chunk_note.side_effect = side_effect
        mock_embedder.embed.return_value = [[0.1] * 768] * 6

        await pipeline.run(sample_vault_config)

        mock_embedder.embed.assert_called_once()
        embed_texts = mock_embedder.embed.call_args[0][0]
        assert len(embed_texts) == 6


class TestIngestPipelineEmbeddings:
    """Contract section 2.3 — embedding assignment."""

    @pytest.mark.unit
    async def test_pipeline_embeddings_assigned_to_chunks(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: embed returns [[0.1]*768, [0.2]*768] → chunks passed to upsert_chunk
        have embedding set to those vectors respectively.
        """
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        vec_a = [0.1] * 768
        vec_b = [0.2] * 768
        mock_embedder.embed.return_value = [vec_a, vec_b]

        await pipeline.run(sample_vault_config)

        upsert_calls = mock_graph_store.upsert_chunk.call_args_list
        assert len(upsert_calls) == 2
        passed_chunk_a = upsert_calls[0][0][0]
        passed_chunk_b = upsert_calls[1][0][0]
        assert passed_chunk_a.embedding == vec_a
        assert passed_chunk_b.embedding == vec_b


class TestIngestPipelineUpsertOrdering:
    """Contract section 2.3 — upsert_note called before upsert_chunk."""

    @pytest.mark.unit
    async def test_pipeline_upsert_note_called_before_upsert_chunk(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: for 1 note with 1 chunk, upsert_note is called before any upsert_chunk call."""
        from knowledge_garden.services.pipeline import IngestPipeline

        call_order: list[str] = []

        async def record_upsert_note(note: Note) -> None:
            call_order.append("upsert_note")

        async def record_upsert_chunk(chunk: Chunk) -> None:
            call_order.append("upsert_chunk")

        mock_graph_store.upsert_note.side_effect = record_upsert_note
        mock_graph_store.upsert_chunk.side_effect = record_upsert_chunk

        note = make_note("Alpha")
        chunk = make_chunk(note, index=0)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
        )

        await pipeline.run(sample_vault_config)

        upsert_note_idx = call_order.index("upsert_note")
        upsert_chunk_idx = call_order.index("upsert_chunk")
        assert upsert_note_idx < upsert_chunk_idx


class TestIngestPipelineProgressCallback:
    """Contract section 2.3 — progress callback behaviour."""

    @pytest.mark.unit
    async def test_pipeline_progress_callback_not_called_for_empty_vault(
        self,
        pipeline,
        mock_parser: MagicMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: empty vault → progress_callback is never called."""
        mock_parser.parse_vault.return_value = []
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        callback.assert_not_called()

    @pytest.mark.unit
    async def test_pipeline_progress_callback_called_once_per_note(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 3 notes → progress_callback called exactly 3 times."""
        notes = [make_note(f"Note{i}") for i in range(3)]
        mock_parser.parse_vault.return_value = notes
        mock_chunker.chunk_note.side_effect = [[make_chunk(n)] for n in notes]
        mock_embedder.embed.return_value = [[0.1] * 768] * 3
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        assert callback.call_count == 3

    @pytest.mark.unit
    async def test_pipeline_progress_callback_receives_correct_args(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: 2 notes titled 'A' and 'B' → callback first call args (1, 2, 'A');
        second call args (2, 2, 'B').
        """
        note_a = make_note("A")
        note_b = make_note("B")
        mock_parser.parse_vault.return_value = [note_a, note_b]
        mock_chunker.chunk_note.side_effect = [[make_chunk(note_a)], [make_chunk(note_b)]]
        mock_embedder.embed.return_value = [[0.1] * 768] * 2
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        assert callback.call_args_list[0] == call(1, 2, "A")
        assert callback.call_args_list[1] == call(2, 2, "B")

    @pytest.mark.unit
    async def test_pipeline_progress_callback_is_optional(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        """Contract: run() called without progress_callback → no exception, returns IngestResult."""
        from knowledge_garden.services.pipeline import IngestResult

        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]

        result = await pipeline.run(sample_vault_config)

        assert isinstance(result, IngestResult)
