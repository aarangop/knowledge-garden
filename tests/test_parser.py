"""Tests for MarkdownParser service — contract: specifications/02_ingestion/contract.md,
section 1.
"""
import uuid

import pytest

from knowledge_garden.services.parser import MarkdownParser


@pytest.fixture
def sample_vault_config(tmp_path):
    from knowledge_garden.config import VaultConfig
    return VaultConfig(name="test_vault", path=str(tmp_path))


class TestParseVault:
    """Contract section 1.2 — parse_vault method tests."""

    @pytest.mark.unit
    def test_parse_vault_empty_directory(self, tmp_path, sample_vault_config):
        """Contract: parse_vault returns [] when directory is empty."""
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert notes == []

    @pytest.mark.unit
    def test_parse_vault_skips_non_md_files(self, tmp_path, sample_vault_config):
        """Contract: parse_vault silently skips non-.md files; returns [] when only non-md files
        exist.
        """
        (tmp_path / "note.txt").write_text("some text")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert notes == []

    @pytest.mark.unit
    def test_parse_vault_single_note(self, tmp_path, sample_vault_config):
        """Contract: parse_vault returns one Note per .md file; title, vault, content are set
        correctly.
        """
        (tmp_path / "hello.md").write_text("# Hello\nWorld")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 1
        assert notes[0].title == "hello"
        assert notes[0].vault == "test_vault"
        assert notes[0].content == "# Hello\nWorld"

    @pytest.mark.unit
    def test_parse_vault_original_path(self, tmp_path, sample_vault_config):
        """Contract: original_path is the relative path from vault root."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.md").write_text("# Nested")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 1
        assert notes[0].original_path == "subdir/nested.md"

    @pytest.mark.unit
    def test_parse_vault_nested_directories(self, tmp_path, sample_vault_config):
        """Contract: parse_vault recursively walks subdirectories and finds all .md files."""
        (tmp_path / "c.md").write_text("# C")
        a_dir = tmp_path / "a"
        a_dir.mkdir()
        (a_dir / "b.md").write_text("# B")
        d_dir = tmp_path / "d"
        e_dir = d_dir / "e"
        e_dir.mkdir(parents=True)
        (e_dir / "f.md").write_text("# F")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 3

    @pytest.mark.unit
    def test_parse_vault_mixed_files(self, tmp_path, sample_vault_config):
        """Contract: parse_vault returns only .md files when directory has mixed file types."""
        (tmp_path / "note.md").write_text("# Note")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n")
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "other.md").write_text("# Other")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 2

    @pytest.mark.unit
    def test_parse_vault_no_links(self, tmp_path, sample_vault_config):
        """Contract: Notes from files with no wikilinks have empty outgoing_links and
        attachment_refs.
        """
        (tmp_path / "plain.md").write_text("No links in this file.")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 1
        assert notes[0].outgoing_links == []
        assert notes[0].attachment_refs == []

    @pytest.mark.unit
    def test_parse_vault_note_has_uuid(self, tmp_path, sample_vault_config):
        """Contract: Each parsed Note has a valid UUID as its id field."""
        (tmp_path / "any.md").write_text("# Any")
        parser = MarkdownParser()
        notes = parser.parse_vault(sample_vault_config)
        assert len(notes) == 1
        note = notes[0]
        assert note.id is not None
        # Validate it is a real UUID by round-tripping through str -> UUID
        parsed = uuid.UUID(str(note.id))
        assert parsed == note.id


class TestExtractWikilinks:
    """Contract section 1.2 — extract_wikilinks method tests."""

    @pytest.mark.unit
    def test_extract_wikilinks_simple(self):
        """Contract: Plain [[target]] is classified as a note link."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("See [[Other Note]]")
        assert note_links == ["Other Note"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_with_alias(self):
        """Contract: [[target|alias]] strips the alias; target goes into note_links."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("See [[target|Display Text]]")
        assert note_links == ["target"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_multiple(self):
        """Contract: Multiple wikilinks in one content string are all extracted in order."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("[[A]] and [[B|alias]] and [[C]]")
        assert note_links == ["A", "B", "C"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_no_links(self):
        """Contract: Content with no wikilinks returns ([], [])."""
        parser = MarkdownParser()
        result = parser.extract_wikilinks("No links here")
        assert result == ([], [])

    @pytest.mark.unit
    def test_extract_wikilinks_empty_string(self):
        """Contract: Empty string content returns ([], [])."""
        parser = MarkdownParser()
        result = parser.extract_wikilinks("")
        assert result == ([], [])

    @pytest.mark.unit
    def test_extract_wikilinks_preserves_duplicates(self):
        """Contract: Duplicate wikilinks are preserved (no deduplication)."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("[[A]] and [[A]]")
        assert note_links == ["A", "A"]

    @pytest.mark.unit
    def test_extract_wikilinks_heading_fragment(self):
        """Contract: Fragment (#heading) is stripped from target; result goes into note_links."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("[[note#heading]]")
        assert note_links == ["note"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_heading_and_alias(self):
        """Contract: Both fragment and alias are stripped; only the base target remains."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("[[note#heading|alias]]")
        assert note_links == ["note"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_transclusion_note(self):
        """Contract: ![[note]] (transclusion of a note target) goes into note_links, not
        attachment_refs.
        """
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("![[note]]")
        assert note_links == ["note"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_transclusion_heading(self):
        """Contract: ![[note#section]] transclusion with fragment — stripped to base note, goes
        into note_links.
        """
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("![[note#section]]")
        assert note_links == ["note"]
        assert attachment_refs == []

    @pytest.mark.unit
    def test_extract_wikilinks_transclusion_image(self):
        """Contract: ![[image.png]] is an attachment reference, not a note link."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("![[image.png]]")
        assert note_links == []
        assert attachment_refs == ["image.png"]

    @pytest.mark.unit
    def test_extract_wikilinks_transclusion_pdf(self):
        """Contract: ![[document.pdf]] is an attachment reference, not a note link."""
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("![[document.pdf]]")
        assert note_links == []
        assert attachment_refs == ["document.pdf"]

    @pytest.mark.unit
    def test_extract_wikilinks_standard_attachment(self):
        """Contract: [[report.pdf]] (non-transclusion) with attachment extension goes into
        attachment_refs.
        """
        parser = MarkdownParser()
        note_links, attachment_refs = parser.extract_wikilinks("[[report.pdf]]")
        assert note_links == []
        assert attachment_refs == ["report.pdf"]

    @pytest.mark.unit
    def test_extract_wikilinks_mixed(self):
        """Contract: Mixed wikilinks are classified correctly; document order preserved within
        each list.
        """
        parser = MarkdownParser()
        content = "[[Note A]] ![[image.png]] [[Note B|alias]] ![[note C]] [[doc.pdf]]"
        note_links, attachment_refs = parser.extract_wikilinks(content)
        assert note_links == ["Note A", "Note B", "note C"]
        assert attachment_refs == ["image.png", "doc.pdf"]


class TestParseFile:
    """Contract section 1.2 — parse_file method tests."""

    @pytest.mark.unit
    def test_parse_file_sets_title_from_stem(self, tmp_path):
        """Contract: Note.title is set to the file stem (filename without extension)."""
        md_file = tmp_path / "My Note.md"
        md_file.write_text("Some content")
        parser = MarkdownParser()
        note = parser.parse_file(md_file, tmp_path, "test_vault")
        assert note.title == "My Note"

    @pytest.mark.unit
    def test_parse_file_sets_outgoing_links(self, tmp_path):
        """Contract: Note.outgoing_links contains resolved note wikilink targets, aliases
        stripped.
        """
        md_file = tmp_path / "links.md"
        md_file.write_text("See [[Link A]] and [[Link B|alias]]")
        parser = MarkdownParser()
        note = parser.parse_file(md_file, tmp_path, "test_vault")
        assert note.outgoing_links == ["Link A", "Link B"]

    @pytest.mark.unit
    def test_parse_file_sets_attachment_refs(self, tmp_path):
        """Contract: Note.attachment_refs contains attachment wikilink targets (non-.md
        extensions).
        """
        md_file = tmp_path / "attachments.md"
        md_file.write_text("![[image.png]] and [[report.pdf]]")
        parser = MarkdownParser()
        note = parser.parse_file(md_file, tmp_path, "test_vault")
        assert note.attachment_refs == ["image.png", "report.pdf"]


# ---------------------------------------------------------------------------
# Spec 13 — Frontmatter preservation
# ---------------------------------------------------------------------------


import logging  # noqa: E402


class TestFrontmatter:
    """Spec 13 §2 / §6.1 — frontmatter parsing in MarkdownParser.parse_file."""

    @staticmethod
    def _write(tmp_path, content: str, name: str = "n.md", binary: bool = False):
        p = tmp_path / name
        if binary:
            p.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        else:
            # Write bytes to control exact line endings (tmp_path.write_text would
            # honor universal newlines on some platforms).
            p.write_bytes(content.encode("utf-8"))
        return p

    @pytest.mark.unit
    def test_no_frontmatter(self, tmp_path):
        """Spec 13 §2.3: file with no `---` block → frontmatter={}, content unchanged, no warning."""
        md = self._write(tmp_path, "# Hello\nWorld")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == "# Hello\nWorld"

    @pytest.mark.unit
    def test_simple_frontmatter(self, tmp_path):
        """Spec 13 §6.1: well-formed mapping → parsed dict; block stripped from content."""
        md = self._write(tmp_path, "---\ntitle: Foo\ntags: [a, b]\n---\n# Body\n")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"title": "Foo", "tags": ["a", "b"]}
        assert note.content == "# Body\n"

    @pytest.mark.unit
    def test_frontmatter_no_trailing_newline(self, tmp_path):
        """Spec 13 §2.3: frontmatter without trailing newline → parsed; body becomes ''."""
        md = self._write(tmp_path, "---\nkey: value\n---")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"key": "value"}
        assert note.content == ""

    @pytest.mark.unit
    def test_frontmatter_crlf(self, tmp_path):
        """Spec 13 §2.3: CRLF line endings handled identically to LF."""
        md = self._write(tmp_path, "---\r\nkey: value\r\n---\r\nbody")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"key": "value"}
        assert note.content == "body"

    @pytest.mark.unit
    def test_empty_frontmatter_block(self, tmp_path, caplog):
        """Spec 13 §2.3 / §6.1: `---\\n---\\nbody` → clean strip; frontmatter={}, content="body";
        NO warning logged."""
        md = self._write(tmp_path, "---\n---\nbody")
        parser = MarkdownParser()
        with caplog.at_level(logging.WARNING, logger="knowledge_garden.services.parser"):
            note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == "body"
        parser_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING
            and r.name == "knowledge_garden.services.parser"
        ]
        assert parser_warnings == [], f"Unexpected warnings: {parser_warnings}"

    @pytest.mark.unit
    def test_whitespace_only_frontmatter_block(self, tmp_path, caplog):
        """Spec 13 §2.3 / §6.1: `---\\n\\n---\\nbody` → clean strip; no warning."""
        md = self._write(tmp_path, "---\n\n---\nbody")
        parser = MarkdownParser()
        with caplog.at_level(logging.WARNING, logger="knowledge_garden.services.parser"):
            note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == "body"
        parser_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING
            and r.name == "knowledge_garden.services.parser"
        ]
        assert parser_warnings == [], f"Unexpected warnings: {parser_warnings}"

    @pytest.mark.unit
    def test_malformed_yaml(self, tmp_path, caplog):
        """Spec 13 §6.1: malformed YAML → frontmatter={}, raw content preserved, WARNING logged."""
        raw = "---\nkey: : :\n---\nbody"
        md = self._write(tmp_path, raw)
        parser = MarkdownParser()
        with caplog.at_level(logging.WARNING, logger="knowledge_garden.services.parser"):
            note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == raw
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and r.name == "knowledge_garden.services.parser"
        ]
        assert warnings, "Expected a WARNING from the parser logger"

    @pytest.mark.unit
    def test_top_level_yaml_list(self, tmp_path, caplog):
        """Spec 13 §6.1: top-level YAML list → frontmatter={}, raw preserved, WARNING logged."""
        raw = "---\n- a\n- b\n---\nbody"
        md = self._write(tmp_path, raw)
        parser = MarkdownParser()
        with caplog.at_level(logging.WARNING, logger="knowledge_garden.services.parser"):
            note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == raw
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and r.name == "knowledge_garden.services.parser"
        ]
        assert warnings, "Expected a WARNING from the parser logger"

    @pytest.mark.unit
    def test_top_level_yaml_scalar(self, tmp_path, caplog):
        """Spec 13 §6.1: top-level YAML scalar → frontmatter={}, raw preserved, WARNING logged."""
        raw = "---\n42\n---\nbody"
        md = self._write(tmp_path, raw)
        parser = MarkdownParser()
        with caplog.at_level(logging.WARNING, logger="knowledge_garden.services.parser"):
            note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == raw
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and r.name == "knowledge_garden.services.parser"
        ]
        assert warnings, "Expected a WARNING from the parser logger"

    @pytest.mark.unit
    def test_frontmatter_nested_dict(self, tmp_path):
        """Spec 13 §2.3: nested dict in frontmatter is preserved."""
        md = self._write(tmp_path, "---\nmeta:\n  k: v\n---\nbody")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"meta": {"k": "v"}}
        assert note.content == "body"

    @pytest.mark.unit
    def test_frontmatter_multiline_string(self, tmp_path):
        """Spec 13 §2.3: YAML literal block (`|`) preserves newlines."""
        md = self._write(tmp_path, "---\nnote: |\n  a\n  b\n---\nbody")
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"note": "a\nb\n"}
        assert note.content == "body"

    @pytest.mark.unit
    def test_dashes_not_at_start(self, tmp_path):
        """Spec 13 §2.3: `---` not at start of file → not treated as frontmatter."""
        raw = "hello\n---\nkey: v\n---\n"
        md = self._write(tmp_path, raw)
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {}
        assert note.content == raw

    @pytest.mark.unit
    def test_wikilink_in_frontmatter_value_extracted(self, tmp_path):
        """Spec 13 §2.3 / §6.1: wikilinks inside frontmatter populate outgoing_links;
        block is still stripped from content."""
        raw = '---\nup: "[[Project]]"\nrelated: "[[Foo]]"\n---\n[[Bar]]\n'
        md = self._write(tmp_path, raw)
        parser = MarkdownParser()
        note = parser.parse_file(md, tmp_path, "v")
        assert note.frontmatter == {"up": "[[Project]]", "related": "[[Foo]]"}
        assert note.content == "[[Bar]]\n"
        assert set(note.outgoing_links) >= {"Project", "Foo", "Bar"}
