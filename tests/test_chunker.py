"""Tests for NoteChunker service — contract: specifications/02_ingestion/contract.md, section 2."""
import pytest

from knowledge_garden.config import ChunkingConfig
from knowledge_garden.models.note import Note
from knowledge_garden.services.chunker import NoteChunker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_chunking_config() -> ChunkingConfig:
    """ChunkingConfig with generous limits for most tests."""
    return ChunkingConfig(max_chunk_size=1000, min_chunk_size=10)


@pytest.fixture
def small_chunking_config() -> ChunkingConfig:
    """ChunkingConfig with tight max_chunk_size to force paragraph splitting."""
    return ChunkingConfig(max_chunk_size=50, min_chunk_size=10)


def make_note(content: str) -> Note:
    """Helper that returns a Note with the given content and fixed metadata."""
    return Note(
        title="test",
        content=content,
        vault="v",
        original_path="test.md",
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestNoteChunker:
    """Contract section 2: NoteChunker interface and splitting rules."""

    # --- no-heading cases ---

    @pytest.mark.unit
    def test_chunk_note_no_headings(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: content with no headings → 1 chunk, heading_context='', index=0."""
        note = make_note("Just some plain text here with enough words.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 1
        assert "plain text" in chunks[0].content
        assert chunks[0].heading_context == ""
        assert chunks[0].index == 0

    @pytest.mark.unit
    def test_chunk_note_no_headings_below_min(
        self, default_chunking_config: ChunkingConfig
    ) -> None:
        """Contract: content with no headings that is shorter than min_chunk_size → []."""
        note = make_note("Hi")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert chunks == []

    @pytest.mark.unit
    def test_chunk_note_empty_content(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: note with empty content → returns []."""
        note = make_note("")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert chunks == []

    # --- single heading cases ---

    @pytest.mark.unit
    def test_chunk_note_single_h2(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: one ## heading → 1 chunk, heading_context='Section', heading not in body."""
        note = make_note("## Section\nSome content here.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 1
        assert chunks[0].heading_context == "Section"
        assert "## Section" not in chunks[0].content

    @pytest.mark.unit
    def test_chunk_note_h1_splits_content(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: H1 headings ARE split points, just like all other heading levels."""
        content = (
            "# Title\n"
            "Intro text that is long enough to meet minimum.\n"
            "## Section\n"
            "Section content that is also long enough."
        )
        note = make_note(content)
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 2
        assert chunks[0].heading_context == "Title"
        assert chunks[1].heading_context == "Section"

    @pytest.mark.unit
    def test_chunk_note_h3_is_split_point(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: ### headings are split points producing chunks with correct heading_context."""
        note = make_note("### SubSection\nEnough content here.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 1
        assert chunks[0].heading_context == "SubSection"

    # --- heading format rules ---

    @pytest.mark.unit
    def test_chunk_note_heading_context_no_hashes(
        self, default_chunking_config: ChunkingConfig
    ) -> None:
        """Contract: heading_context stores heading text WITHOUT # characters or extra
        whitespace.
        """
        note = make_note("## My Heading\nBody text that meets the minimum size.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 1
        assert "#" not in chunks[0].heading_context
        assert chunks[0].heading_context == "My Heading"

    @pytest.mark.unit
    def test_chunk_note_heading_not_in_body(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: heading line is NOT present in chunk.content; body text IS present."""
        note = make_note("## Section\nBody text.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 1
        assert "## Section" not in chunks[0].content
        assert "Body text." in chunks[0].content

    # --- multiple heading cases ---

    @pytest.mark.unit
    def test_chunk_note_multiple_h2(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: 3 ## sections each with sufficient content → 3 chunks with indices 0, 1, 2."""
        content = (
            "## Alpha\nContent for alpha section that is long enough.\n"
            "## Beta\nContent for beta section that is long enough.\n"
            "## Gamma\nContent for gamma section that is long enough."
        )
        note = make_note(content)
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) == 3
        assert [c.index for c in chunks] == [0, 1, 2]

    @pytest.mark.unit
    def test_chunk_note_sequential_indices(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: chunk index values are sequential starting at 0 across all 4 sections."""
        content = (
            "## One\nFirst section content that is long enough to pass.\n"
            "## Two\nSecond section content that is long enough to pass.\n"
            "## Three\nThird section content that is long enough to pass.\n"
            "## Four\nFourth section content that is long enough to pass."
        )
        note = make_note(content)
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert [c.index for c in chunks] == [0, 1, 2, 3]

    # --- chunk metadata rules ---

    @pytest.mark.unit
    def test_chunk_note_sets_note_id(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: chunk.note_id == note.id for all chunks."""
        note = make_note("## Section\nContent long enough to survive min check.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.note_id == note.id

    @pytest.mark.unit
    def test_chunk_note_embedding_is_none(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: embedding is always None on freshly produced chunks."""
        note = make_note("## Section\nContent long enough to survive min check.")
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.embedding is None

    # --- oversized / paragraph splitting ---

    @pytest.mark.unit
    def test_chunk_note_oversized_section_split_by_paragraph(
        self, small_chunking_config: ChunkingConfig
    ) -> None:
        """Contract: section text > max_chunk_size is further split on \\n\\n boundaries."""
        # Each paragraph is ~40 chars; total section ~120 chars → must split with max=50
        para1 = "First paragraph with enough text."
        para2 = "Second paragraph with enough text."
        para3 = "Third paragraph with enough text."
        content = f"## Section\n{para1}\n\n{para2}\n\n{para3}"
        note = make_note(content)
        chunker = NoteChunker(small_chunking_config)
        chunks = chunker.chunk_note(note)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content.strip()) <= small_chunking_config.max_chunk_size

    @pytest.mark.unit
    def test_chunk_note_paragraph_split_inherits_heading_context(
        self, small_chunking_config: ChunkingConfig
    ) -> None:
        """Contract: all sub-chunks from paragraph splitting inherit the same heading_context."""
        para1 = "First paragraph with enough text here."
        para2 = "Second paragraph with enough text here."
        content = f"## Section\n{para1}\n\n{para2}"
        note = make_note(content)
        chunker = NoteChunker(small_chunking_config)
        chunks = chunker.chunk_note(note)
        # Must produce at least 2 chunks (oversized section split)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert chunk.heading_context == "Section"

    # --- below-minimum discard ---

    @pytest.mark.unit
    def test_chunk_note_below_min_discarded(self, default_chunking_config: ChunkingConfig) -> None:
        """Contract: sections with stripped body shorter than min_chunk_size are dropped."""
        # "Hi" is 2 chars, well below min_chunk_size=10
        content = (
            "## Tiny\nHi\n"
            "## Big\nThis section has content that is definitely long enough to keep."
        )
        note = make_note(content)
        chunker = NoteChunker(default_chunking_config)
        chunks = chunker.chunk_note(note)
        # The tiny section must be discarded; only the big section survives
        assert all(chunk.heading_context != "Tiny" for chunk in chunks)
        assert any(chunk.heading_context == "Big" for chunk in chunks)
