"""Tests for domain models — contract: specifications/01_foundation/contract.md, section 2"""
from uuid import UUID

import pytest
from pydantic import ValidationError

from knowledge_garden.models.note import Chunk, Note, Vault


class TestNoteModel:
    """Contract section: 2.2 — Note model tests"""

    @pytest.mark.unit
    def test_note_default_id(self):
        """Contract: Create Note without explicit id → UUID is auto-generated."""
        note = Note(
            title="My Note",
            content="Some content",
            vault="vault_a",
            original_path="folder/my_note.md",
        )
        assert note.id is not None
        assert isinstance(note.id, UUID)

    @pytest.mark.unit
    def test_note_unique_ids(self):
        """Contract: Two Notes created without explicit id → different UUIDs."""
        note_a = Note(
            title="Note A",
            content="Content A",
            vault="vault_a",
            original_path="note_a.md",
        )
        note_b = Note(
            title="Note B",
            content="Content B",
            vault="vault_a",
            original_path="note_b.md",
        )
        assert note_a.id != note_b.id

    @pytest.mark.unit
    def test_note_serialization(self):
        """Contract: Note → model_dump() → dict with all fields; UUID serializes to string
        when mode='json'.
        """
        note = Note(
            title="Serialized Note",
            content="Hello world",
            vault="vault_x",
            original_path="serialized.md",
        )

        # model_dump() without mode — UUID should be a UUID object
        raw = note.model_dump()
        assert isinstance(raw, dict)
        assert "id" in raw
        assert "title" in raw
        assert "content" in raw
        assert "vault" in raw
        assert "original_path" in raw
        assert "outgoing_links" in raw
        assert "resolved_links" in raw

        # model_dump(mode="json") — UUID must serialize to a string
        json_dict = note.model_dump(mode="json")
        assert isinstance(json_dict["id"], str)

    @pytest.mark.unit
    def test_note_required_fields(self):
        """Contract: Omit title → ValidationError (missing required fields)."""
        with pytest.raises(ValidationError):
            Note(
                content="Some content",
                vault="vault_a",
                original_path="note.md",
            )

    @pytest.mark.unit
    def test_note_empty_links_default(self):
        """Contract: Create Note without links → outgoing_links and resolved_links are empty
        lists.
        """
        note = Note(
            title="No Links",
            content="Plain note",
            vault="vault_a",
            original_path="no_links.md",
        )
        assert note.outgoing_links == []
        assert note.resolved_links == []

    @pytest.mark.unit
    def test_note_attachment_refs_default_empty(self):
        """Contract: spec 02 section 0.2 — Create Note without attachment_refs →
        attachment_refs == [].
        """
        note = Note(title="t", content="c", vault="v", original_path="p.md")
        assert note.attachment_refs == []


class TestChunkModel:
    """Contract section: 2.2 — Chunk model tests"""

    @pytest.mark.unit
    def test_chunk_requires_note_id(self):
        """Contract: Create Chunk without note_id → ValidationError."""
        with pytest.raises(ValidationError):
            Chunk(
                content="A chunk of text",
                index=0,
            )

    @pytest.mark.unit
    def test_chunk_embedding_optional(self):
        """Contract: Create Chunk without embedding → embedding is None."""
        from uuid import uuid4
        chunk = Chunk(
            note_id=uuid4(),
            content="Chunk without embedding",
            index=0,
        )
        assert chunk.embedding is None

    @pytest.mark.unit
    def test_chunk_embedding_accepts_floats(self):
        """Contract: Create Chunk with embedding list → stored correctly."""
        from uuid import uuid4
        embedding = [0.1, 0.2, 0.3, 0.4]
        chunk = Chunk(
            note_id=uuid4(),
            content="Chunk with embedding",
            index=1,
            embedding=embedding,
        )
        assert chunk.embedding == embedding
        assert all(isinstance(v, float) for v in chunk.embedding)


class TestVaultModel:
    """Contract section: 2.2 — Vault model tests"""

    @pytest.mark.unit
    def test_vault_model(self):
        """Contract: Create Vault with name and path → fields accessible."""
        vault = Vault(name="my_vault", path="/home/user/obsidian/my_vault")
        assert vault.name == "my_vault"
        assert vault.path == "/home/user/obsidian/my_vault"
