"""Tests for the kg CLI — contract: specifications/03_cli/contract.md, sections 4 and 5."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from knowledge_garden.config import AppSettings, BusinessConfig, EmbeddingConfig, VaultConfig
from knowledge_garden.models.note import Note

# Import the service-layer SearchResult dataclass (does not exist yet in red phase).
try:
    from knowledge_garden.services.graph_store import SearchResult as ServiceSearchResult
    _SEARCH_RESULT_AVAILABLE = True
except ImportError:
    ServiceSearchResult = None  # type: ignore[assignment, misc]
    _SEARCH_RESULT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer CliRunner for invoking CLI commands synchronously.

    Contract: section 4.6 — cli_runner fixture.
    """
    return CliRunner()


def _mock_settings() -> MagicMock:
    """Return a MagicMock standing in for AppSettings in CLI tests."""
    return MagicMock(spec=AppSettings)


@pytest.fixture
def sample_config(tmp_path):
    """Write a minimal valid business config.yaml and return (BusinessConfig, Path).

    Contract: section 4.6 — sample_config fixture.
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "vaults:\n"
        "  - name: my_vault\n"
        "    path: /tmp/my_vault\n"
    )
    return BusinessConfig.from_yaml(config_path), config_path


def _make_note(title: str = "Note A", vault: str = "my_vault") -> Note:
    """Build a Note for use in CLI tests."""
    return Note(
        title=title,
        content="Some content.",
        vault=vault,
        original_path=f"{title}.md",
    )


# ---------------------------------------------------------------------------
# TestIngestCommand
# ---------------------------------------------------------------------------


class TestIngestCommand:
    """Contract section 4.3 — kg ingest command."""

    @pytest.mark.unit
    def test_ingest_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: ingest happy path exits with code 0.

        Patch _run_ingest as AsyncMock returning None; also patch helpers that
        would hit the filesystem or real services.
        """
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=1, chunks_created=2, chunks_skipped=0, duration_seconds=0.1
            )
            result = cli_runner.invoke(app, ["ingest", "my_vault"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_ingest_command_calls_run_ingest_with_vault_name(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: ingest command invokes _run_ingest and passes the correct vault config."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=0, chunks_created=0, chunks_skipped=0, duration_seconds=0.0
            )
            cli_runner.invoke(app, ["ingest", "my_vault"])
        mock_run.assert_called_once()
        # First positional arg passed to _run_ingest must be the VaultConfig for "my_vault"
        vault_arg = mock_run.call_args.args[0]
        assert vault_arg.name == "my_vault"

    @pytest.mark.unit
    def test_ingest_command_unknown_vault_exits_nonzero(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: ingest with a vault name not in config exits with non-zero code."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
        ):
            result = cli_runner.invoke(app, ["ingest", "missing_vault"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_ingest_vault_not_found(self, cli_runner: CliRunner) -> None:
        """Contract: ingest with unknown vault prints 'not found' message and exits 1."""
        from knowledge_garden.cli import app

        config_obj = BusinessConfig(vaults=[VaultConfig(name="other", path="/x")])
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
        ):
            result = cli_runner.invoke(app, ["ingest", "missing_vault"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @pytest.mark.unit
    def test_ingest_missing_config_file(self, cli_runner: CliRunner) -> None:
        """Contract: ingest pointing to a nonexistent config file exits 1 and reports error."""
        from knowledge_garden.cli import app

        with patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()):
            result = cli_runner.invoke(
                app, ["ingest", "vault", "--config", "/nonexistent/config.yaml"]
            )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @pytest.mark.unit
    def test_ingest_happy_path(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: ingest happy path outputs 'Notes parsed' and 'Chunks created'."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=3, chunks_created=12, chunks_skipped=0, duration_seconds=1.5
            )
            result = cli_runner.invoke(app, ["ingest", "my_vault"])
        assert result.exit_code == 0
        assert "Notes parsed" in result.output or "notes parsed" in result.output.lower()
        assert "Chunks created" in result.output or "chunks created" in result.output.lower()

    @pytest.mark.unit
    def test_ingest_prints_summary_table(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: ingest prints a summary table containing the result numbers."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=3, chunks_created=12, chunks_skipped=0, duration_seconds=1.5
            )
            result = cli_runner.invoke(app, ["ingest", "my_vault"])
        assert "3" in result.output
        assert "12" in result.output
        # duration should appear as 1.5 or 1.50
        assert "1.5" in result.output

    @pytest.mark.unit
    def test_ingest_unknown_provider_exits(self, cli_runner: CliRunner) -> None:
        """Contract: ingest with unknown embedding provider exits 1 and reports error."""
        from knowledge_garden.cli import app

        config_obj = BusinessConfig(
            vaults=[VaultConfig(name="my_vault", path="/tmp/my_vault")],
            embedding=EmbeddingConfig(provider="unknown"),
        )
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
        ):
            result = cli_runner.invoke(app, ["ingest", "my_vault"])
        assert result.exit_code == 1
        assert "Unknown embedding provider" in result.output

    @pytest.mark.unit
    def test_ingest_vault_not_found_message(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: exit code is 1 when _run_ingest raises typer.Exit(1)."""
        import typer

        from knowledge_garden.cli import app

        config_obj, _ = sample_config

        async def _raise(*args, **kwargs):
            raise typer.Exit(1)

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", side_effect=_raise),
        ):
            result = cli_runner.invoke(app, ["ingest", "my_vault"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# TestNotesCommand
# ---------------------------------------------------------------------------


class TestNotesCommand:
    """Contract section 4.4 — kg notes command."""

    @pytest.mark.unit
    def test_notes_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: notes command exits with code 0 on success."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            result = cli_runner.invoke(app, ["notes"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_notes_command_calls_run_notes_no_filter(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: notes with no --vault option calls _run_notes with vault_filter=None."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            cli_runner.invoke(app, ["notes"])
        mock_run.assert_called_once()
        # vault_filter keyword arg must be None
        _, kwargs = mock_run.call_args
        assert kwargs.get("vault_filter") is None

    @pytest.mark.unit
    def test_notes_command_vault_option_passed(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: --vault option is forwarded to _run_notes as vault_filter='my_vault'."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            cli_runner.invoke(app, ["notes", "--vault", "my_vault"])
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert kwargs.get("vault_filter") == "my_vault"

    @pytest.mark.unit
    def test_notes_empty_graph(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: notes with empty graph prints 'No notes found'."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            result = cli_runner.invoke(app, ["notes"])
        assert result.exit_code == 0
        assert "No notes found" in result.output

    @pytest.mark.unit
    def test_notes_lists_all(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: notes lists all notes, showing each note's title."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        notes = [_make_note("Alpha"), _make_note("Beta")]
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = notes
            result = cli_runner.invoke(app, ["notes"])
        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Beta" in result.output

    @pytest.mark.unit
    def test_notes_vault_filter(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: notes --vault filters output to only that vault's notes."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        notes_a = [_make_note("NoteX", vault="vaultA"), _make_note("NoteY", vault="vaultA")]
        _make_note("NoteZ", vault="vaultB")  # not returned by mock — confirms filter

        # Simulate server-side filter: helper is called with vault_filter="vaultA",
        # returns only vaultA notes (the CLI renders whatever _run_notes returns).
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = notes_a  # filtered result
            result = cli_runner.invoke(app, ["notes", "--vault", "vaultA"])
        assert "NoteX" in result.output
        assert "NoteY" in result.output
        assert "NoteZ" not in result.output

    @pytest.mark.unit
    def test_notes_id_truncated(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: displayed note ID is the first 8 characters of the UUID string."""
        from knowledge_garden.cli import app
        from knowledge_garden.models.note import Note

        config_obj, _ = sample_config
        fixed_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
        note = Note(
            id=fixed_id,
            title="SomeNote",
            content="content",
            vault="my_vault",
            original_path="SomeNote.md",
        )
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = [note]
            result = cli_runner.invoke(app, ["notes"])
        expected_prefix = str(fixed_id)[:8]  # "12345678"
        assert expected_prefix in result.output

    @pytest.mark.unit
    def test_notes_shows_link_count(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: notes shows the count of outgoing links in the Links column."""
        from knowledge_garden.cli import app
        from knowledge_garden.models.note import Note

        config_obj, _ = sample_config
        note = Note(
            title="LinkedNote",
            content="content",
            vault="my_vault",
            original_path="LinkedNote.md",
            outgoing_links=["A", "B", "C"],
        )
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_notes", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = [note]
            result = cli_runner.invoke(app, ["notes"])
        assert "3" in result.output


# ---------------------------------------------------------------------------
# TestStatusCommand
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Contract section 4.5 — kg status command."""

    @pytest.mark.unit
    def test_status_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: status command exits with code 0 on success."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            result = cli_runner.invoke(app, ["status"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_status_command_calls_run_status(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: status command invokes _run_status exactly once."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            cli_runner.invoke(app, ["status"])
        mock_run.assert_called_once()

    @pytest.mark.unit
    def test_status_empty_graph(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: status with empty graph prints 'No data in graph'."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            result = cli_runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "No data in graph" in result.output

    @pytest.mark.unit
    def test_status_shows_vault_breakdown(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: status shows per-vault note counts and total count."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        notes = (
            [_make_note(f"n{i}", vault="vault1") for i in range(3)]
            + [_make_note("n3", vault="vault2")]
        )
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = notes
            result = cli_runner.invoke(app, ["status"])
        assert "vault1" in result.output
        assert "vault2" in result.output
        assert "3" in result.output
        assert "1" in result.output
        assert "4" in result.output

    @pytest.mark.unit
    def test_status_vaults_sorted_alphabetically(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: status lists vaults in ascending alphabetical order."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        notes = [
            _make_note("nz", vault="zeta"),
            _make_note("na", vault="alpha"),
            _make_note("nb", vault="beta"),
        ]
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = notes
            result = cli_runner.invoke(app, ["status"])
        pos_alpha = result.output.index("alpha")
        pos_beta = result.output.index("beta")
        pos_zeta = result.output.index("zeta")
        assert pos_alpha < pos_beta < pos_zeta

    @pytest.mark.unit
    def test_status_total_row(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: status prints a 'Total' row with the total note count."""
        from knowledge_garden.cli import app

        config_obj, _ = sample_config
        notes = (
            [_make_note(f"n{i}", vault="vault1") for i in range(3)]
            + [_make_note(f"m{i}", vault="vault2") for i in range(2)]
        )
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_status", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = notes
            result = cli_runner.invoke(app, ["status"])
        assert "Total" in result.output
        assert "5" in result.output


# ---------------------------------------------------------------------------
# TestHelpCommand
# ---------------------------------------------------------------------------


class TestLinkCommand:
    """Contract section — kg link command."""

    @pytest.mark.unit
    def test_link_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: link happy path exits with code 0."""
        from knowledge_garden.cli import app
        from knowledge_garden.services.linker import LinkResult

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_link", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = LinkResult(
                chunks_processed=10,
                similarity_edges_created=5,
                note_relationships_derived=3,
                duration_seconds=0.5,
            )
            result = cli_runner.invoke(app, ["link"])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_link_command_prints_summary_table(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: link command prints result table with chunks, edges, relationships."""
        from knowledge_garden.cli import app
        from knowledge_garden.services.linker import LinkResult

        config_obj, _ = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_link", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = LinkResult(
                chunks_processed=10,
                similarity_edges_created=5,
                note_relationships_derived=3,
                duration_seconds=1.2,
            )
            result = cli_runner.invoke(app, ["link"])
        assert "10" in result.output
        assert "5" in result.output
        assert "3" in result.output
        assert "1.2" in result.output

    @pytest.mark.unit
    def test_link_missing_config_file(self, cli_runner: CliRunner) -> None:
        """Contract: link with nonexistent config exits 1 and reports error."""
        from knowledge_garden.cli import app

        with patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()):
            result = cli_runner.invoke(
                app, ["link", "--config", "/nonexistent/config.yaml"]
            )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


class TestExportCommand:
    """Contract section 5 — kg export command."""

    @pytest.mark.unit
    def test_export_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: export happy path exits with code 0."""
        from knowledge_garden.cli import app
        from knowledge_garden.services.exporter import ExportResult

        config_obj, config_path = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_export", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = ExportResult(
                notes_exported=2, files_written=2, duration_seconds=0.5
            )
            result = cli_runner.invoke(app, ["export", "--config", str(config_path)])
        assert result.exit_code == 0

    @pytest.mark.unit
    def test_export_command_prints_table(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: export prints a summary table containing 'Notes exported' and the count."""
        from knowledge_garden.cli import app
        from knowledge_garden.services.exporter import ExportResult

        config_obj, config_path = sample_config
        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_export", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = ExportResult(
                notes_exported=4, files_written=4, duration_seconds=1.1
            )
            result = cli_runner.invoke(app, ["export", "--config", str(config_path)])
        assert "Notes exported" in result.output
        assert "4" in result.output

    @pytest.mark.unit
    def test_export_command_config_not_found(self, cli_runner: CliRunner) -> None:
        """Contract: export with nonexistent config file exits with code 1."""
        from knowledge_garden.cli import app

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch(
                "knowledge_garden.cli._load_business_config",
                side_effect=FileNotFoundError("not found"),
            ),
        ):
            result = cli_runner.invoke(
                app, ["export", "--config", "/nonexistent/config.yaml"]
            )
        assert result.exit_code == 1

    @pytest.mark.unit
    def test_export_command_settings_error(self, cli_runner: CliRunner) -> None:
        """Contract: export with bad AppSettings exits with code 1."""
        from knowledge_garden.cli import app

        with patch(
            "knowledge_garden.cli._load_app_settings",
            side_effect=Exception("settings error"),
        ):
            result = cli_runner.invoke(app, ["export"])
        assert result.exit_code == 1


class TestHelpCommand:
    """Contract section 4.1 — top-level app help."""

    @pytest.mark.unit
    def test_help_exits_zero(self, cli_runner: CliRunner) -> None:
        """Contract: --help flag exits with code 0."""
        from knowledge_garden.cli import app

        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# TestSearchCommand — spec 10, section 9
# ---------------------------------------------------------------------------


def _make_service_search_result_cli(
    note_id: str = "aabb0000-0000-0000-0000-000000000001",
    title: str = "Search Result Note",
    source_vault: str = "vault_a",
    original_path: str = "search_result.md",
    score: float = 0.92,
    snippet: str = "a short snippet from the matching chunk",
    heading_context: str = "## Results Section",
):
    """Build a service-layer SearchResult for CLI tests."""
    if not _SEARCH_RESULT_AVAILABLE:
        return MagicMock(
            note_id=note_id,
            title=title,
            source_vault=source_vault,
            original_path=original_path,
            score=score,
            snippet=snippet,
            heading_context=heading_context,
        )
    return ServiceSearchResult(  # type: ignore[call-arg]
        note_id=note_id,
        title=title,
        source_vault=source_vault,
        original_path=original_path,
        score=score,
        snippet=snippet,
        heading_context=heading_context,
    )


class TestSearchCommand:
    """Contract section 9 — kg search command (spec 10)."""

    @pytest.mark.unit
    def test_search_command_exits_zero(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: search happy path exits with code 0."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config
        search_result = _make_service_search_result_cli()

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_search", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = [search_result]
            result = cli_runner.invoke(
                app, ["search", "hello", "--config", str(config_path)]
            )

        assert result.exit_code == 0

    @pytest.mark.unit
    def test_search_command_prints_table(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: search output contains note title and formatted score."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config
        search_result = _make_service_search_result_cli(
            title="My Important Note",
            score=0.9234,
        )

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_search", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = [search_result]
            result = cli_runner.invoke(
                app, ["search", "hello", "--config", str(config_path)]
            )

        assert result.exit_code == 0
        assert "My Important Note" in result.output
        assert "0.9234" in result.output

    @pytest.mark.unit
    def test_search_command_no_results(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: search with no results prints 'No results found.' and exits 0."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_search", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            result = cli_runner.invoke(
                app, ["search", "hello", "--config", str(config_path)]
            )

        assert result.exit_code == 0
        assert "No results found" in result.output

    @pytest.mark.unit
    def test_search_command_vault_flag(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: --vault flag is forwarded to _run_search as vault='myvault'."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_search", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            cli_runner.invoke(
                app,
                ["search", "hello", "--vault", "myvault", "--config", str(config_path)],
            )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        # vault may be passed positionally or as keyword
        call_args = mock_run.call_args
        all_args = list(call_args.args) + list(call_args.kwargs.values())
        assert "myvault" in all_args or call_kwargs.get("vault") == "myvault"

    @pytest.mark.unit
    def test_search_command_limit_flag_overrides_config(
        self, cli_runner: CliRunner, sample_config
    ) -> None:
        """Contract: --limit 5 → _run_search called with limit=5."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_search", new_callable=AsyncMock) as mock_run,
        ):
            mock_run.return_value = []
            cli_runner.invoke(
                app,
                ["search", "hello", "--limit", "5", "--config", str(config_path)],
            )

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # limit=5 must appear somewhere in the call
        all_values = list(call_args.args) + list(call_args.kwargs.values())
        assert 5 in all_values or call_args.kwargs.get("limit") == 5

    @pytest.mark.unit
    def test_search_command_config_not_found(self, cli_runner: CliRunner) -> None:
        """Contract: _load_business_config raises FileNotFoundError → exit code 1."""
        from knowledge_garden.cli import app

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch(
                "knowledge_garden.cli._load_business_config",
                side_effect=FileNotFoundError("not found"),
            ),
        ):
            result = cli_runner.invoke(
                app, ["search", "hello", "--config", "/nonexistent/config.yaml"]
            )

        assert result.exit_code == 1

    @pytest.mark.unit
    def test_search_command_settings_error(self, cli_runner: CliRunner) -> None:
        """Contract: _load_app_settings raises Exception → exit code 1."""
        from knowledge_garden.cli import app

        with patch(
            "knowledge_garden.cli._load_app_settings",
            side_effect=Exception("bad settings"),
        ):
            result = cli_runner.invoke(app, ["search", "hello"])

        assert result.exit_code == 1

    @pytest.mark.unit
    def test_search_command_embedder_error(self, cli_runner: CliRunner, sample_config) -> None:
        """Contract: _make_embedder raises ValueError → exit code 1."""
        from knowledge_garden.cli import app

        config_obj, config_path = sample_config

        with (
            patch("knowledge_garden.cli._load_app_settings", return_value=_mock_settings()),
            patch("knowledge_garden.cli._load_business_config", return_value=config_obj),
            patch(
                "knowledge_garden.cli._make_embedder",
                side_effect=ValueError("unknown provider"),
            ),
        ):
            result = cli_runner.invoke(
                app, ["search", "hello", "--config", str(config_path)]
            )

        assert result.exit_code == 1
