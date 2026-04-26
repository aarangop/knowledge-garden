"""NoteChunker service — splits a Note into Chunk objects based on heading structure."""

from __future__ import annotations

import re

from knowledge_garden.config import ChunkingConfig
from knowledge_garden.models.note import Chunk, Note

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class NoteChunker:
    """Splits a Note into Chunk objects based on heading structure and size limits.

    Splitting rules:
    1. Content is split at ALL markdown heading levels: #, ##, ###, ####,
       #####, ######. Every heading line is a split point.
    2. The heading line itself is NOT included in the chunk body content.
       heading_context stores the heading text with all leading # characters
       and surrounding whitespace stripped (e.g., "## My Section" -> "My Section").
       Content before the first heading of any level has heading_context = "".
    3. If a section's body text length exceeds max_chunk_size, it is further
       split by double-newline paragraph boundaries (splitting on "\\n\\n").
       Each paragraph sub-chunk inherits the same heading_context.
    4. Chunks with fewer than min_chunk_size characters (after stripping
       whitespace) are discarded.
    5. Surviving chunks are assigned sequential index values starting at 0.
    6. note_id is set to the parent Note.id on every chunk.
    7. embedding is always None.
    """

    def __init__(self, config: ChunkingConfig) -> None:
        """
        Parameters
        ----------
        config:
            ChunkingConfig providing max_chunk_size and min_chunk_size.
        """
        self._config = config

    def chunk_note(self, note: Note) -> list[Chunk]:
        """Split a Note into an ordered list of Chunk objects.

        Parameters
        ----------
        note:
            The Note to chunk. Uses note.content and note.id.

        Returns
        -------
        list[Chunk]
            Ordered list of chunks (by index). May be empty if all sections
            are smaller than min_chunk_size.
        """
        content = note.content
        if not content:
            return []

        # Find all heading matches
        matches = list(HEADING_RE.finditer(content))

        # Build list of (heading_context, body_text) sections
        sections: list[tuple[str, str]] = []

        if not matches:
            # No headings — entire content is one section
            sections.append(("", content))
        else:
            # Content before the first heading
            first_match_start = matches[0].start()
            pre_heading_body = content[:first_match_start]
            sections.append(("", pre_heading_body))

            # Each heading section: from end of heading line to start of next heading
            for i, match in enumerate(matches):
                heading_context = match.group(2).strip()
                # Body starts after the heading line (end of match)
                body_start = match.end()
                # Body ends at the start of the next heading, or end of content
                body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
                body = content[body_start:body_end]
                sections.append((heading_context, body))

        # Process sections into chunks
        chunks: list[Chunk] = []
        index = 0

        for heading_context, body in sections:
            stripped_body = body.strip()

            if len(stripped_body) == 0:
                # Empty body — discard
                continue

            if len(stripped_body) <= self._config.max_chunk_size:
                # Within size limit — apply min check
                if len(stripped_body) >= self._config.min_chunk_size:
                    chunks.append(
                        Chunk(
                            note_id=note.id,
                            content=stripped_body,
                            heading_context=heading_context,
                            index=index,
                            embedding=None,
                        )
                    )
                    index += 1
            else:
                # Oversized — split on double newline
                paragraphs = stripped_body.split("\n\n")
                for para in paragraphs:
                    para_stripped = para.strip()
                    if len(para_stripped) >= self._config.min_chunk_size:
                        chunks.append(
                            Chunk(
                                note_id=note.id,
                                content=para_stripped,
                                heading_context=heading_context,
                                index=index,
                                embedding=None,
                            )
                        )
                        index += 1

        return chunks
