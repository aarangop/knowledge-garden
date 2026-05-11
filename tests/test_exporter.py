"""Tests for VaultExporter — contract: specifications/09_export/contract.md"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from knowledge_garden.models.note import Note
from knowledge_garden.services.exporter import (
    ExportPhase,
    VaultExporter,
)

# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_note():
    """Factory fixture: make_note(title, vault, content='', note_id=None) -> Note.

    Contract: section 8 — make_note fixture for exporter tests.
    """

    def _factory(
        title: str,
        vault: str,
        content: str = "",
        note_id: uuid.UUID | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> Note:
        if note_id is None:
            note_id = uuid.uuid4()
        return Note(
            id=note_id,
            title=title,
            content=content,
            vault=vault,
            original_path=f"{title}.md",
            frontmatter=frontmatter or {},
        )

    return _factory


# ---------------------------------------------------------------------------
# Spec 13 helper — extract the frontmatter block from composed file output
# ---------------------------------------------------------------------------


def _split_frontmatter_block(text: str) -> tuple[str, str]:
    """Return (yaml_body_str, rest_of_file).

    The composed file always begins with `---\\n<yaml>\\n---\\n` per spec 13 §4.3.
    """
    assert text.startswith("---\n"), f"Expected frontmatter fence at start, got: {text[:20]!r}"
    rest = text[4:]
    end = rest.find("\n---\n")
    assert end != -1, "Expected closing `---` fence followed by newline"
    yaml_body = rest[:end]
    after = rest[end + len("\n---\n"):]
    return yaml_body, after


def _parse_frontmatter(text: str) -> dict[str, Any]:
    yaml_body, _ = _split_frontmatter_block(text)
    parsed = yaml.safe_load(yaml_body)
    assert isinstance(parsed, dict), f"Expected dict frontmatter, got {type(parsed).__name__}"
    return parsed


# ---------------------------------------------------------------------------
# TestVaultExporter — unit tests
# ---------------------------------------------------------------------------


class TestVaultExporter:
    """Contract section 4 — VaultExporter service."""

    # ------------------------------------------------------------------
    # _build_stem_map
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_build_stem_map_no_conflicts(self, make_note):
        """Contract: 2 notes with distinct titles produce stems equal to their titles."""
        n_a = make_note("A", "v1")
        n_b = make_note("B", "v1")
        result = VaultExporter._build_stem_map([n_a, n_b])
        assert result[n_a.id] == "A"
        assert result[n_b.id] == "B"

    @pytest.mark.unit
    def test_build_stem_map_conflict_same_title_different_vaults(self, make_note):
        """Contract: 2 notes sharing title 'Note' from different vaults get vault suffix."""
        n1 = make_note("Note", "v1")
        n2 = make_note("Note", "v2")
        result = VaultExporter._build_stem_map([n1, n2])
        assert result[n1.id] == "Note (v1)"
        assert result[n2.id] == "Note (v2)"

    @pytest.mark.unit
    def test_build_stem_map_conflict_three_notes_same_title(self, make_note):
        """Contract: 3 notes sharing title 'Note' from vaults v1,v2,v3 all get vault suffix."""
        n1 = make_note("Note", "v1")
        n2 = make_note("Note", "v2")
        n3 = make_note("Note", "v3")
        result = VaultExporter._build_stem_map([n1, n2, n3])
        assert result[n1.id] == "Note (v1)"
        assert result[n2.id] == "Note (v2)"
        assert result[n3.id] == "Note (v3)"

    @pytest.mark.unit
    def test_build_stem_map_single_note(self, make_note):
        """Contract: single note — stem equals note.title (no suffix)."""
        n = make_note("Lone Note", "vault_x")
        result = VaultExporter._build_stem_map([n])
        assert result[n.id] == "Lone Note"

    # ------------------------------------------------------------------
    # _build_references_section
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_build_references_both_present(self):
        """Contract: links_to and related_to non-empty → output contains both subsections."""
        result = VaultExporter._build_references_section(
            links_to=["A", "B"], related_to=["C"]
        )
        assert "### Links" in result
        assert "### Discovered Connections" in result
        assert "[[A]]" in result
        assert "[[B]]" in result
        assert "[[C]]" in result

    @pytest.mark.unit
    def test_build_references_links_only(self):
        """Contract: related_to empty → ### Discovered Connections is absent."""
        result = VaultExporter._build_references_section(links_to=["A"], related_to=[])
        assert "### Links" in result
        assert "### Discovered Connections" not in result

    @pytest.mark.unit
    def test_build_references_related_only(self):
        """Contract: links_to empty → ### Links is absent."""
        result = VaultExporter._build_references_section(links_to=[], related_to=["C"])
        assert "### Discovered Connections" in result
        assert "### Links" not in result

    @pytest.mark.unit
    def test_build_references_both_empty(self):
        """Contract: both empty → returns empty string."""
        result = VaultExporter._build_references_section(links_to=[], related_to=[])
        assert result == ""

    @pytest.mark.unit
    def test_build_references_links_alphabetical(self):
        """Contract: caller passes pre-sorted links_to; output preserves that order."""
        # Caller is responsible for sorting; test verifies when caller sorts alphabetically
        # the output matches that order.
        sorted_links = sorted(["Zebra", "Apple", "Mango"])  # Apple, Mango, Zebra
        result = VaultExporter._build_references_section(
            links_to=sorted_links, related_to=[]
        )
        pos_apple = result.index("Apple")
        pos_mango = result.index("Mango")
        pos_zebra = result.index("Zebra")
        assert pos_apple < pos_mango < pos_zebra

    @pytest.mark.unit
    def test_build_references_related_score_order(self):
        """Contract: caller passes pre-sorted (desc) related_to; output preserves that order."""
        # caller passes desc order: High before Low
        result = VaultExporter._build_references_section(
            links_to=[], related_to=["High", "Low"]
        )
        pos_high = result.index("High")
        pos_low = result.index("Low")
        assert pos_high < pos_low

    # ------------------------------------------------------------------
    # _compose_file
    # ------------------------------------------------------------------

    @pytest.mark.unit
    def test_compose_file_includes_frontmatter(self, make_note):
        """Spec 13 §6.3: composed file begins with a YAML frontmatter block whose
        parsed content equals the three garden keys (title, source_vault, garden_id)."""
        garden_id = uuid.uuid4()
        note = make_note("My Note", "v1", note_id=garden_id)
        result = VaultExporter._compose_file(note, "My Note", "")
        parsed = _parse_frontmatter(result)
        assert parsed == {
            "title": "My Note",
            "source_vault": "v1",
            "garden_id": str(garden_id),
        }

    @pytest.mark.unit
    def test_compose_file_includes_content(self, make_note):
        """Contract: note.content appears verbatim in the composed file."""
        note = make_note("N", "v1", content="Hello world")
        result = VaultExporter._compose_file(note, "N", "")
        assert "Hello world" in result

    @pytest.mark.unit
    def test_compose_file_with_references(self, make_note):
        """Contract: non-empty references_section is appended to the file."""
        note = make_note("N", "v1", content="Body text")
        refs = "## References\n\n### Links\n- [[A]]\n"
        result = VaultExporter._compose_file(note, "N", refs)
        assert "## References" in result
        assert "[[A]]" in result

    @pytest.mark.unit
    def test_compose_file_no_references(self, make_note):
        """Contract: empty references_section → '## References' is absent from output."""
        note = make_note("N", "v1", content="Body text")
        result = VaultExporter._compose_file(note, "N", "")
        assert "## References" not in result

    @pytest.mark.unit
    def test_compose_file_ends_with_newline(self, make_note):
        """Contract: composed file content ends with a single newline character."""
        note = make_note("N", "v1", content="Some content")
        result = VaultExporter._compose_file(note, "N", "")
        assert result.endswith("\n")

    # ------------------------------------------------------------------
    # export — integration with mock graph store
    # ------------------------------------------------------------------

    @pytest.mark.unit
    async def test_export_writes_files(self, make_note, mock_graph_store, tmp_path):
        """Contract: export writes one .md file per note; files_written == 2."""
        n_a = make_note("Alpha", "v1")
        n_b = make_note("Beta", "v1")
        mock_graph_store.get_all_notes.return_value = [n_a, n_b]
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        exporter = VaultExporter(mock_graph_store, tmp_path)
        result = await exporter.export()

        written_files = list(tmp_path.glob("*.md"))
        assert len(written_files) == 2
        assert result.files_written == 2

    @pytest.mark.unit
    async def test_export_creates_output_dir(self, make_note, mock_graph_store, tmp_path):
        """Contract: output_dir is created if it does not exist."""
        output_dir = tmp_path / "new_subdir" / "deep"
        mock_graph_store.get_all_notes.return_value = [make_note("A", "v1")]
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        exporter = VaultExporter(mock_graph_store, output_dir)
        await exporter.export()

        assert output_dir.exists()
        assert output_dir.is_dir()

    @pytest.mark.unit
    async def test_export_conflict_resolution_filename(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: conflicting titles produce disambiguated filenames with vault suffix."""
        n1 = make_note("Note", "v1")
        n2 = make_note("Note", "v2")
        mock_graph_store.get_all_notes.return_value = [n1, n2]
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        exporter = VaultExporter(mock_graph_store, tmp_path)
        await exporter.export()

        assert (tmp_path / "Note (v1).md").exists()
        assert (tmp_path / "Note (v2).md").exists()

    @pytest.mark.unit
    async def test_export_references_links_to_alphabetical(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: LINKS_TO targets are sorted alphabetically by stem in output."""
        note_a = make_note("Note A", "v1")
        note_zebra = make_note("Zebra", "v1")
        note_apple = make_note("Apple", "v1")

        mock_graph_store.get_all_notes.return_value = [note_a, note_zebra, note_apple]

        def get_relationships(note_id):
            if note_id == note_a.id:
                return {"LINKS_TO": [(str(note_zebra.id), 1.0), (str(note_apple.id), 1.0)]}
            return {}

        mock_graph_store.get_note_relationships_with_scores.side_effect = get_relationships

        exporter = VaultExporter(mock_graph_store, tmp_path)
        await exporter.export()

        # Note A's stem is "Note A" (no conflict)
        file_content = (tmp_path / "Note A.md").read_text()
        pos_apple = file_content.index("Apple")
        pos_zebra = file_content.index("Zebra")
        assert pos_apple < pos_zebra, "Apple should appear before Zebra in ### Links"

    @pytest.mark.unit
    async def test_export_references_related_to_score_desc(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: RELATED_TO targets are sorted by score descending in output."""
        note_a = make_note("Note A", "v1")
        note_b = make_note("Note B", "v1")
        note_c = make_note("Note C", "v1")

        mock_graph_store.get_all_notes.return_value = [note_a, note_b, note_c]

        def get_relationships(note_id):
            if note_id == note_a.id:
                return {
                    "RELATED_TO": [
                        (str(note_b.id), 0.9),
                        (str(note_c.id), 0.7),
                    ]
                }
            return {}

        mock_graph_store.get_note_relationships_with_scores.side_effect = get_relationships

        exporter = VaultExporter(mock_graph_store, tmp_path)
        await exporter.export()

        file_content = (tmp_path / "Note A.md").read_text()
        pos_b = file_content.index("Note B")
        pos_c = file_content.index("Note C")
        assert pos_b < pos_c, "Note B (score 0.9) should appear before Note C (score 0.7)"

    @pytest.mark.unit
    async def test_export_skips_orphaned_targets(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: RELATED_TO target UUID not in get_all_notes result is silently skipped."""
        note_a = make_note("Note A", "v1")
        orphan_id = str(uuid.uuid4())

        mock_graph_store.get_all_notes.return_value = [note_a]

        def get_relationships(note_id):
            if note_id == note_a.id:
                return {"RELATED_TO": [(orphan_id, 0.95)]}
            return {}

        mock_graph_store.get_note_relationships_with_scores.side_effect = get_relationships

        exporter = VaultExporter(mock_graph_store, tmp_path)
        # Should not raise KeyError
        result = await exporter.export()
        assert result.notes_exported == 1

    @pytest.mark.unit
    async def test_export_idempotent_overwrites(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: running export twice to the same directory succeeds; files are overwritten."""
        n = make_note("MyNote", "v1", content="Version 1")
        mock_graph_store.get_all_notes.return_value = [n]
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        exporter = VaultExporter(mock_graph_store, tmp_path)
        await exporter.export()

        # Update content and run again
        n_v2 = make_note("MyNote", "v1", content="Version 2", note_id=n.id)
        mock_graph_store.get_all_notes.return_value = [n_v2]

        result2 = await exporter.export()
        assert result2.files_written == 1
        assert (tmp_path / "MyNote.md").exists()

    @pytest.mark.unit
    async def test_export_progress_callback_called(
        self, make_note, mock_graph_store, tmp_path
    ):
        """Contract: progress_callback is invoked once per note with ExportPhase.WRITING."""
        notes = [make_note(f"Note {i}", "v1") for i in range(3)]
        mock_graph_store.get_all_notes.return_value = notes
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        callback = MagicMock()
        exporter = VaultExporter(mock_graph_store, tmp_path)
        await exporter.export(progress_callback=callback)

        assert callback.call_count == 3
        for c in callback.call_args_list:
            phase = c.args[0]
            assert phase == ExportPhase.WRITING

    @pytest.mark.unit
    async def test_export_result_shape(self, make_note, mock_graph_store, tmp_path):
        """Contract: ExportResult has notes_exported==3, files_written==3, duration_seconds>=0."""
        notes = [make_note(f"N{i}", "v1") for i in range(3)]
        mock_graph_store.get_all_notes.return_value = notes
        mock_graph_store.get_note_relationships_with_scores.return_value = {}

        exporter = VaultExporter(mock_graph_store, tmp_path)
        result = await exporter.export()

        assert result.notes_exported == 3
        assert result.files_written == 3
        assert result.duration_seconds >= 0

    @pytest.mark.unit
    async def test_export_empty_graph(self, mock_graph_store, tmp_path):
        """Contract: empty graph → ExportResult(notes_exported=0, files_written=0); no files."""
        mock_graph_store.get_all_notes.return_value = []

        exporter = VaultExporter(mock_graph_store, tmp_path)
        result = await exporter.export()

        assert result.notes_exported == 0
        assert result.files_written == 0
        assert result.duration_seconds >= 0
        assert list(tmp_path.glob("*.md")) == []


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestExporterIntegration:
    """Integration tests requiring a live Neo4j instance."""

    @pytest.mark.integration
    async def test_exporter_integration_end_to_end(self, neo4j_store, tmp_path):
        """Contract: section 8 integration test — 2 notes, LINKS_TO, derive_related_to,
        export produces 2 files; note A contains ### Links with [[Note B]].
        """
        note_a = Note(
            title="Note A",
            content="Content of Note A",
            vault="test_vault",
            original_path="note_a.md",
            outgoing_links=["Note B"],
        )
        note_b = Note(
            title="Note B",
            content="Content of Note B",
            vault="test_vault",
            original_path="note_b.md",
        )

        await neo4j_store.upsert_note(note_a)
        await neo4j_store.upsert_note(note_b)
        await neo4j_store.create_link(note_a.id, note_b.id, "LINKS_TO")

        # Attempt derive_related_to (may create no edges if no SIMILAR_TO edges, but must not fail)
        await neo4j_store.derive_related_to()

        exporter = VaultExporter(neo4j_store, tmp_path)
        await exporter.export()

        # 2 files exist
        md_files = list(tmp_path.glob("*.md"))
        assert len(md_files) == 2, f"Expected 2 .md files, got {len(md_files)}: {md_files}"

        # Note A's file contains ### Links with [[Note B]]
        note_a_file = tmp_path / "Note A.md"
        assert note_a_file.exists(), "Note A.md not found in output dir"
        content = note_a_file.read_text()
        assert "### Links" in content, "### Links section missing from Note A.md"
        assert "[[Note B]]" in content, "[[Note B]] link missing from Note A.md"


# ---------------------------------------------------------------------------
# Spec 13 — _compose_file frontmatter merge
# ---------------------------------------------------------------------------


class TestComposeFileFrontmatterMerge:
    """Spec 13 §4 / §6.3 — _compose_file merges note.frontmatter with garden keys."""

    @pytest.mark.unit
    def test_compose_file_merges_user_frontmatter(self, make_note):
        """Spec 13 §6.3: user keys appear first; garden keys appended after."""
        garden_id = uuid.uuid4()
        note = make_note(
            "My Note", "v1", note_id=garden_id, frontmatter={"tags": ["a", "b"]}
        )
        result = VaultExporter._compose_file(note, "My Note", "")
        parsed = _parse_frontmatter(result)
        assert parsed == {
            "tags": ["a", "b"],
            "title": "My Note",
            "source_vault": "v1",
            "garden_id": str(garden_id),
        }
        keys = list(parsed.keys())
        assert keys[0] == "tags"

    @pytest.mark.unit
    def test_compose_file_garden_keys_override_user_keys(self, make_note):
        """Spec 13 §4.2: garden keys overwrite user keys with the same name."""
        garden_id = uuid.uuid4()
        note = make_note(
            "Stem Title",
            "real_vault",
            note_id=garden_id,
            frontmatter={"title": "User Title", "garden_id": "fake"},
        )
        result = VaultExporter._compose_file(note, "Stem Title", "")
        parsed = _parse_frontmatter(result)
        assert parsed["title"] == "Stem Title"
        assert parsed["garden_id"] == str(garden_id)

    @pytest.mark.unit
    def test_compose_file_no_user_frontmatter(self, make_note):
        """Spec 13 §4.4: empty user frontmatter → exactly the three garden keys."""
        note = make_note("N", "v1", frontmatter={})
        result = VaultExporter._compose_file(note, "N", "")
        parsed = _parse_frontmatter(result)
        assert set(parsed.keys()) == {"title", "source_vault", "garden_id"}

    @pytest.mark.unit
    def test_compose_file_unicode_frontmatter(self, make_note):
        """Spec 13 §4.4: allow_unicode=True keeps the literal character (no \\xNN)."""
        note = make_note("N", "v1", frontmatter={"summary": "café"})
        result = VaultExporter._compose_file(note, "N", "")
        yaml_body, _ = _split_frontmatter_block(result)
        assert "café" in yaml_body
        # No escaped form
        assert "\\xe9" not in yaml_body
        assert "\\u" not in yaml_body

    @pytest.mark.unit
    def test_compose_file_nested_user_frontmatter(self, make_note):
        """Spec 13 §4.4: nested dict round-trips through YAML."""
        note = make_note("N", "v1", frontmatter={"meta": {"k": "v"}})
        result = VaultExporter._compose_file(note, "N", "")
        parsed = _parse_frontmatter(result)
        assert parsed["meta"] == {"k": "v"}

    @pytest.mark.unit
    def test_compose_file_single_frontmatter_block(self, make_note):
        """Spec 13 §4.3: output has exactly two `---` fence lines (open + close)."""
        note = make_note("N", "v1", frontmatter={"tags": ["a"]}, content="body")
        result = VaultExporter._compose_file(note, "N", "")
        lines = result.split("\n")
        fence_count = len([line for line in lines if line.strip() == "---"])
        assert fence_count == 2, f"Expected exactly 2 fence lines, got {fence_count}"

    @pytest.mark.unit
    def test_compose_file_user_keys_appear_before_garden_keys(self, make_note):
        """Spec 13 §4.2: with no collisions, user keys precede garden keys in order."""
        garden_id = uuid.uuid4()
        note = make_note(
            "Stem", "v1", note_id=garden_id, frontmatter={"a": 1, "b": 2}
        )
        result = VaultExporter._compose_file(note, "Stem", "")
        parsed = _parse_frontmatter(result)
        assert list(parsed.keys()) == ["a", "b", "title", "source_vault", "garden_id"]
