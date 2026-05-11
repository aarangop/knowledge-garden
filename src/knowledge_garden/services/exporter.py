from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

import yaml

if TYPE_CHECKING:
    from knowledge_garden.models.note import Note
    from knowledge_garden.services.graph_store import GraphStore


@dataclass
class ExportResult:
    notes_exported: int
    files_written: int
    duration_seconds: float


class ExportPhase(StrEnum):
    WRITING = "writing"


ExportProgressCallback = Callable[[ExportPhase, int, int, str], None]


class VaultExporter:
    def __init__(
        self,
        graph_store: GraphStore,
        output_dir: str | Path,
    ) -> None:
        self._graph_store = graph_store
        self._output_dir = Path(output_dir)

    async def export(
        self,
        progress_callback: ExportProgressCallback | None = None,
    ) -> ExportResult:
        start = time.monotonic()
        notes = await self._graph_store.get_all_notes()
        stem_map = self._build_stem_map(notes)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        total = len(notes)

        sorted_notes = sorted(notes, key=lambda n: stem_map[n.id])

        for idx, note in enumerate(sorted_notes):
            stem = stem_map[note.id]
            rels = await self._graph_store.get_note_relationships_with_scores(note.id)

            links_to_raw = rels.get("LINKS_TO", [])
            related_to_raw = rels.get("RELATED_TO", [])

            links_to_stems = sorted(
                stem_map[UUID(tid)]
                for tid, _ in links_to_raw
                if UUID(tid) in stem_map
            )
            related_to_stems = [
                stem_map[UUID(tid)]
                for tid, _ in sorted(related_to_raw, key=lambda x: -x[1])
                if UUID(tid) in stem_map
            ]

            references_section = self._build_references_section(links_to_stems, related_to_stems)
            content = self._compose_file(note, stem, references_section)
            (self._output_dir / f"{stem}.md").write_text(content, encoding="utf-8")

            if progress_callback is not None:
                progress_callback(ExportPhase.WRITING, idx + 1, total, stem)

        elapsed = time.monotonic() - start
        return ExportResult(notes_exported=total, files_written=total, duration_seconds=elapsed)

    @staticmethod
    def _build_conflict_map(notes: list[Note]) -> dict[str, list[Note]]:
        result: dict[str, list[Note]] = {}
        for note in notes:
            result.setdefault(note.title, []).append(note)
        return result

    @staticmethod
    def _build_stem_map(notes: list[Note]) -> dict[UUID, str]:
        conflict_map = VaultExporter._build_conflict_map(notes)
        stem_map: dict[UUID, str] = {}
        for title, group in conflict_map.items():
            if len(group) == 1:
                stem_map[group[0].id] = title
            else:
                for note in group:
                    stem_map[note.id] = f"{title} ({note.vault})"
        return stem_map

    @staticmethod
    def _build_references_section(
        links_to: list[str],
        related_to: list[str],
    ) -> str:
        if not links_to and not related_to:
            return ""

        parts = ["## References\n"]
        if links_to:
            parts.append("\n### Links\n")
            for stem in links_to:
                parts.append(f"- [[{stem}]]\n")
        if related_to:
            parts.append("\n### Discovered Connections\n")
            for stem in related_to:
                parts.append(f"- [[{stem}]]\n")

        return "".join(parts) + "\n"

    @staticmethod
    def _compose_file(note: Note, stem: str, references_section: str) -> str:
        merged: dict[str, Any] = dict(note.frontmatter)
        merged["title"] = stem
        merged["source_vault"] = note.vault
        merged["garden_id"] = str(note.id)

        yaml_block = yaml.safe_dump(
            merged,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        frontmatter = f"---\n{yaml_block}---\n"

        body = f"\n{note.content}\n"
        if references_section:
            body += f"\n{references_section}"
        return frontmatter + body
