"""Tests for IngestPipeline — contract: specifications/07_pipeline_dedup/contract.md."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from knowledge_garden.config import ChunkingConfig, VaultConfig
from knowledge_garden.models.note import Chunk, Note
from knowledge_garden.services.chunker import NoteChunker
from knowledge_garden.services.parser import MarkdownParser
from knowledge_garden.services.pipeline import IngestPhase, IngestPipeline


def make_note(title: str = "Note A") -> Note:
    return Note(
        title=title,
        content="## Section\n\n" + "word " * 50,
        vault="test_vault",
        original_path=f"{title}.md",
    )


def make_chunk(note: Note, index: int = 0) -> Chunk:
    return Chunk(note_id=note.id, content="Chunk content.", index=index)


@pytest.fixture
def default_chunking_config() -> ChunkingConfig:
    return ChunkingConfig(max_chunk_size=1000, min_chunk_size=10)


@pytest.fixture
def mock_parser() -> MagicMock:
    return MagicMock(spec=MarkdownParser)


@pytest.fixture
def mock_chunker() -> MagicMock:
    return MagicMock(spec=NoteChunker)


@pytest.fixture
def sample_vault_config() -> VaultConfig:
    return VaultConfig(name="test_vault", path="/tmp/test_vault")


@pytest.fixture
def pipeline(
    mock_parser: MagicMock,
    mock_chunker: MagicMock,
    mock_embedder: AsyncMock,
    mock_graph_store: AsyncMock,
) -> IngestPipeline:
    return IngestPipeline(
        parser=mock_parser,
        chunker=mock_chunker,
        embedder=mock_embedder,
        graph_store=mock_graph_store,
    )


class TestIngestResult:
    """Contract: IngestResult has chunks_skipped field."""

    @pytest.mark.unit
    def test_ingest_result_has_chunks_skipped(self) -> None:
        from knowledge_garden.services.pipeline import IngestResult

        result = IngestResult(
            notes_parsed=1,
            chunks_created=2,
            chunks_skipped=3,
            duration_seconds=0.5,
        )
        assert result.chunks_skipped == 3


class TestIngestPhase:
    """Contract: IngestPhase has CHUNKING, DEDUP, UPSERT."""

    @pytest.mark.unit
    def test_ingest_phase_values(self) -> None:
        assert IngestPhase.CHUNKING == "chunking"
        assert IngestPhase.DEDUP == "dedup"
        assert IngestPhase.UPSERT == "upsert"

    @pytest.mark.unit
    def test_ingest_phase_no_embedding_or_indexing(self) -> None:
        assert not hasattr(IngestPhase, "EMBEDDING")
        assert not hasattr(IngestPhase, "INDEXING")


class TestIngestPipelineResult:
    @pytest.mark.unit
    async def test_pipeline_result_is_ingest_result(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        from knowledge_garden.services.pipeline import IngestResult

        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert isinstance(result, IngestResult)
        assert result.chunks_skipped == 0

    @pytest.mark.unit
    async def test_pipeline_result_duration_non_negative(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.duration_seconds >= 0


class TestIngestPipelineEmptyVault:
    @pytest.mark.unit
    async def test_pipeline_empty_vault(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        mock_parser.parse_vault.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 0
        assert result.chunks_created == 0
        assert result.chunks_skipped == 0
        mock_embedder.embed.assert_not_called()
        mock_graph_store.upsert_note.assert_not_called()


class TestIngestPipelineSingleNote:
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
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        mock_embedder.embed.return_value = [[0.1] * 768, [0.2] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 1
        assert result.chunks_created == 2
        mock_graph_store.upsert_note.assert_called_once()
        assert mock_graph_store.upsert_chunk.call_count == 2


class TestIngestPipelineMultipleNotes:
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
        notes = [make_note(f"Note{i}") for i in range(3)]
        chunks = [make_chunk(note, index=0) for note in notes]
        mock_parser.parse_vault.return_value = notes
        mock_chunker.chunk_note.side_effect = [[c] for c in chunks]
        mock_embedder.embed.side_effect = lambda texts: [[0.1] * 768] * len(texts)
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.notes_parsed == 3
        assert result.chunks_created == 3
        assert mock_graph_store.upsert_note.call_count == 3
        assert mock_graph_store.upsert_chunk.call_count == 3

    @pytest.mark.unit
    async def test_pipeline_embed_called_per_batch(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        notes = [make_note("A"), make_note("B")]

        def side_effect(note: Note) -> list[Chunk]:
            return [make_chunk(note, index=i) for i in range(3)]

        mock_parser.parse_vault.return_value = notes
        mock_chunker.chunk_note.side_effect = side_effect
        mock_embedder.embed.side_effect = lambda texts: [[0.1] * 768] * len(texts)
        mock_graph_store.find_similar_chunks.return_value = []

        await pipeline.run(sample_vault_config)

        all_embed_texts = [c[0][0] for c in mock_embedder.embed.call_args_list]
        assert sum(len(t) for t in all_embed_texts) == 6


class TestIngestPipelineEmbeddings:
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
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        vec_a = [0.1] * 768
        vec_b = [0.2] * 768
        mock_embedder.embed.return_value = [vec_a, vec_b]
        mock_graph_store.find_similar_chunks.return_value = []

        await pipeline.run(sample_vault_config)

        upsert_calls = mock_graph_store.upsert_chunk.call_args_list
        assert len(upsert_calls) == 2
        passed_chunk_a = upsert_calls[0][0][0]
        passed_chunk_b = upsert_calls[1][0][0]
        assert passed_chunk_a.embedding == vec_a
        assert passed_chunk_b.embedding == vec_b


class TestIngestPipelineUpsertOrdering:
    @pytest.mark.unit
    async def test_pipeline_upsert_note_called_before_upsert_chunk(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        call_order: list[str] = []

        async def record_upsert_note(note: Note) -> None:
            call_order.append("upsert_note")

        async def record_upsert_chunk(chunk: Chunk) -> None:
            call_order.append("upsert_chunk")

        mock_graph_store.upsert_note.side_effect = record_upsert_note
        mock_graph_store.upsert_chunk.side_effect = record_upsert_chunk
        mock_graph_store.find_similar_chunks.return_value = []

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

    @pytest.mark.unit
    async def test_pipeline_upsert_note_called_once_per_note_across_batches(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunks = [make_chunk(note, index=i) for i in range(4)]
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = chunks
        mock_embedder.embed.side_effect = lambda texts: [[0.1] * 768] * len(texts)
        mock_graph_store.find_similar_chunks.return_value = []

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
            embed_batch_size=2,
        )

        await pipeline.run(sample_vault_config)

        assert mock_graph_store.upsert_note.call_count == 1
        assert mock_graph_store.upsert_chunk.call_count == 4


class TestIngestPipelineDedup:
    """Contract: dedup skips chunks that match existing index."""

    @pytest.mark.unit
    async def test_pipeline_dedup_skips_identical_chunks(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        mock_embedder.embed.return_value = [[0.1] * 768, [0.2] * 768]

        existing_chunk = make_chunk(note, index=99)
        mock_graph_store.find_similar_chunks.side_effect = [
            [(existing_chunk, 0.99)],
            [],
        ]

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
        )

        result = await pipeline.run(sample_vault_config)

        assert result.chunks_skipped == 1
        assert result.chunks_created == 1
        assert mock_graph_store.upsert_chunk.call_count == 1

    @pytest.mark.unit
    async def test_pipeline_dedup_keeps_novel_chunks(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk_a = make_chunk(note, index=0)
        chunk_b = make_chunk(note, index=1)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk_a, chunk_b]
        mock_embedder.embed.return_value = [[0.1] * 768, [0.2] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert result.chunks_skipped == 0
        assert result.chunks_created == 2

    @pytest.mark.unit
    async def test_pipeline_dedup_threshold_from_constructor(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
            dedup_threshold=0.9,
        )

        await pipeline.run(sample_vault_config)

        mock_graph_store.find_similar_chunks.assert_called_once()
        call_kwargs = mock_graph_store.find_similar_chunks.call_args
        assert call_kwargs.kwargs.get("threshold") == 0.9

    @pytest.mark.unit
    async def test_pipeline_dedup_fail_open_on_exception(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]
        mock_graph_store.find_similar_chunks.side_effect = RuntimeError("index unavailable")

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
        )

        result = await pipeline.run(sample_vault_config)

        assert result.chunks_skipped == 0
        assert result.chunks_created == 1
        mock_graph_store.upsert_chunk.assert_called_once()

    @pytest.mark.unit
    async def test_pipeline_all_chunks_duplicate_note_still_upserted(
        self,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]

        existing_chunk = make_chunk(note, index=99)
        mock_graph_store.find_similar_chunks.return_value = [(existing_chunk, 0.99)]

        pipeline = IngestPipeline(
            parser=mock_parser,
            chunker=mock_chunker,
            embedder=mock_embedder,
            graph_store=mock_graph_store,
        )

        result = await pipeline.run(sample_vault_config)

        assert result.chunks_skipped == 1
        assert result.chunks_created == 0
        mock_graph_store.upsert_note.assert_called_once()
        mock_graph_store.upsert_chunk.assert_not_called()


class TestIngestPipelineProgressCallback:
    @pytest.mark.unit
    async def test_pipeline_progress_callback_not_called_for_empty_vault(
        self,
        pipeline,
        mock_parser: MagicMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        mock_parser.parse_vault.return_value = []
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        callback.assert_not_called()

    @pytest.mark.unit
    async def test_pipeline_progress_callback_reports_all_phases(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        notes = [make_note(f"Note{i}") for i in range(3)]
        mock_parser.parse_vault.return_value = notes
        mock_chunker.chunk_note.side_effect = [[make_chunk(n)] for n in notes]
        mock_embedder.embed.side_effect = lambda texts: [[0.1] * 768] * len(texts)
        mock_graph_store.find_similar_chunks.return_value = []
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        chunking_calls = [c for c in callback.call_args_list if c[0][0] == IngestPhase.CHUNKING]
        dedup_calls = [c for c in callback.call_args_list if c[0][0] == IngestPhase.DEDUP]
        upsert_calls = [c for c in callback.call_args_list if c[0][0] == IngestPhase.UPSERT]
        assert len(chunking_calls) == 3
        assert len(dedup_calls) >= 1
        assert len(upsert_calls) >= 1

    @pytest.mark.unit
    async def test_pipeline_progress_callback_receives_correct_chunking_args(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        note_a = make_note("A")
        note_b = make_note("B")
        mock_parser.parse_vault.return_value = [note_a, note_b]
        mock_chunker.chunk_note.side_effect = [[make_chunk(note_a)], [make_chunk(note_b)]]
        mock_embedder.embed.side_effect = lambda texts: [[0.1] * 768] * len(texts)
        mock_graph_store.find_similar_chunks.return_value = []
        callback = MagicMock()

        await pipeline.run(sample_vault_config, progress_callback=callback)

        chunking_calls = [c for c in callback.call_args_list if c[0][0] == IngestPhase.CHUNKING]
        assert chunking_calls[0] == call(IngestPhase.CHUNKING, 1, 2, "A")
        assert chunking_calls[1] == call(IngestPhase.CHUNKING, 2, 2, "B")

    @pytest.mark.unit
    async def test_pipeline_progress_callback_is_optional(
        self,
        pipeline,
        mock_parser: MagicMock,
        mock_chunker: MagicMock,
        mock_embedder: AsyncMock,
        mock_graph_store: AsyncMock,
        sample_vault_config: VaultConfig,
    ) -> None:
        from knowledge_garden.services.pipeline import IngestResult

        note = make_note("Alpha")
        chunk = make_chunk(note)
        mock_parser.parse_vault.return_value = [note]
        mock_chunker.chunk_note.return_value = [chunk]
        mock_embedder.embed.return_value = [[0.1] * 768]
        mock_graph_store.find_similar_chunks.return_value = []

        result = await pipeline.run(sample_vault_config)

        assert isinstance(result, IngestResult)
