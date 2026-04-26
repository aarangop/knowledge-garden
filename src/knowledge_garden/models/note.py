from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Vault(BaseModel):
    """Represents a source Obsidian vault."""

    name: str
    path: str  # absolute path to vault root


class Note(BaseModel):
    """A single Obsidian note, parsed from a .md file."""

    id: UUID = Field(default_factory=uuid4)
    title: str  # filename without .md
    content: str  # raw markdown content
    vault: str  # source vault name
    original_path: str  # relative path within vault
    outgoing_links: list[str] = []  # raw wikilink targets (unresolved)
    attachment_refs: list[str] = []  # non-note wikilink targets (images, PDFs, etc.)
    resolved_links: list[UUID] = []  # resolved Note IDs after link resolution


class Chunk(BaseModel):
    """A semantic segment of a Note."""

    id: UUID = Field(default_factory=uuid4)
    note_id: UUID  # parent Note
    content: str  # chunk text
    heading_context: str = ""  # nearest heading above this chunk
    index: int  # position within the note (0-based)
    embedding: list[float] | None = None
