"""Markdown parser service for Knowledge Garden.

Parses Obsidian-flavoured markdown vaults into Note objects.
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from knowledge_garden.config import VaultConfig
from knowledge_garden.models.note import Note

logger = logging.getLogger(__name__)

FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(\r?\n|\Z)",
    re.DOTALL | re.MULTILINE,
)

# Matches both transclusion (![[...]]) and standard ([[...]]) wikilinks.
# Group 1: "!" if transclusion prefix present, else empty string.
# Group 2: the raw inner content (everything between [[ and ]]).
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")

# File extensions that identify attachment targets (non-note files).
ATTACHMENT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".pdf",
    ".mp4",
    ".mov",
    ".webm",
    ".zip",
    ".csv",
    ".xlsx",
}


class MarkdownParser:
    """Parses a vault directory into Note objects.

    Walks the vault path recursively, reads every .md file,
    extracts wikilinks, and returns Note objects. Does not embed
    or write to any storage backend.
    """

    def extract_wikilinks(self, content: str) -> tuple[list[str], list[str]]:
        """Classify all [[...]] and ![[...]] patterns in markdown content.

        Classification rules (applied after stripping #fragment and |alias
        from the raw target):

        - If the resolved target has no file extension, or has a .md
          extension -> note link -> goes into note_links.
        - If the resolved target has any other file extension -> attachment
          reference -> goes into attachment_refs.
        - ![[target]] where target resolves to a note -> inline transclusion;
          treated as a note link (goes into note_links).
        - ![[file.png]] -> attachment reference.

        Duplicates are preserved (raw extraction, no dedup).

        Parameters
        ----------
        content:
            Raw markdown text.

        Returns
        -------
        tuple[list[str], list[str]]
            (note_links, attachment_refs)
            note_links      -- ordered list of resolved note target strings
            attachment_refs -- ordered list of attachment filename strings
        """
        note_links: list[str] = []
        attachment_refs: list[str] = []

        for match in WIKILINK_RE.finditer(content):
            inner = match.group(2)
            # Strip alias: take only the part before "|"
            inner = inner.split("|")[0]
            # Strip fragment: take only the part before "#"
            inner = inner.split("#")[0]
            target = inner.strip()

            suffix = Path(target).suffix.lower()
            if suffix in ATTACHMENT_EXTENSIONS:
                attachment_refs.append(target)
            else:
                note_links.append(target)

        return note_links, attachment_refs

    def parse_file(self, file_path: Path, vault_root: Path, vault_name: str) -> Note:
        """Parse a single .md file into a Note.

        Parameters
        ----------
        file_path:
            Absolute path to the .md file.
        vault_root:
            Absolute path to the vault root (used to compute original_path).
        vault_name:
            The vault identifier string (from VaultConfig.name).

        Returns
        -------
        Note
            title           = file_path.stem (filename without extension)
            content         = raw text of the file
            vault           = vault_name
            original_path   = str(file_path.relative_to(vault_root))
            outgoing_links  = note wikilink targets (fragments and aliases stripped)
            attachment_refs = attachment wikilink targets (non-.md extensions)
        """
        raw = file_path.read_text(encoding="utf-8")
        note_links, attachment_refs = self.extract_wikilinks(raw)

        frontmatter: dict[str, Any] = {}
        body = raw
        match = FRONTMATTER_RE.match(raw)
        if match is not None:
            yaml_body = match.group(1)
            try:
                parsed = yaml.safe_load(yaml_body)
            except yaml.YAMLError as exc:
                logger.warning(
                    "Malformed YAML frontmatter; ignoring",
                    extra={"path": str(file_path), "error": str(exc)},
                )
            else:
                if parsed is None:
                    body = raw[match.end():]
                elif isinstance(parsed, dict):
                    frontmatter = parsed
                    body = raw[match.end():]
                else:
                    logger.warning(
                        "YAML frontmatter is not a mapping; ignoring",
                        extra={
                            "path": str(file_path),
                            "type": type(parsed).__name__,
                        },
                    )

        return Note(
            title=file_path.stem,
            content=body,
            vault=vault_name,
            original_path=str(file_path.relative_to(vault_root)),
            outgoing_links=note_links,
            attachment_refs=attachment_refs,
            frontmatter=frontmatter,
        )

    def parse_vault(self, vault_config: VaultConfig) -> list[Note]:
        """Walk vault_config.path recursively and parse all .md files.

        Parameters
        ----------
        vault_config:
            VaultConfig with .name (vault identifier) and .path
            (absolute path to the vault root directory).

        Returns
        -------
        list[Note]
            One Note per .md file found. Files that are not .md are
            silently skipped. Returns [] if the directory is empty or
            contains no .md files.
        """
        vault_root = Path(vault_config.path)
        return [
            self.parse_file(p, vault_root, vault_config.name)
            for p in sorted(vault_root.rglob("*.md"))
        ]
