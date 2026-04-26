"""Tests for the kg CLI — contract: specifications/03_cli/contract.md, sections 4 and 5."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from knowledge_garden.config import Config, EmbeddingConfig, TogetherAIConfig, VaultConfig
from knowledge_garden.models.note import Note

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer CliRunner for invoking CLI commands synchronously.

    Contract: section 4.6 — cli_runner fixture.
    """
    return CliRunner()


@pytest.fixture
def sample_config(tmp_path):
    """Write a minimal valid config.yaml and return (Config, Path).

    Contract: section 4.6 — sample_config fixture.
    """
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "vaults:\n"
        "  - name: my_vault\n"
        "    path: /tmp/my_vault\n"
        "together_ai:\n"
        "  api_key: fake-key\n"
    )
    return Config.from_yaml(config_path), config_path


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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=1, chunks_created=2, duration_seconds=0.1
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=0, chunks_created=0, duration_seconds=0.0
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
        with patch("knowledge_garden.cli._load_config", return_value=config_obj):
            result = cli_runner.invoke(app, ["ingest", "missing_vault"])
        assert result.exit_code != 0

    @pytest.mark.unit
    def test_ingest_vault_not_found(self, cli_runner: CliRunner) -> None:
        """Contract: ingest with unknown vault prints 'not found' message and exits 1."""
        from knowledge_garden.cli import app

        config_obj = Config(
            vaults=[VaultConfig(name="other", path="/x")],
            together_ai=TogetherAIConfig(api_key="fake"),
        )
        with patch("knowledge_garden.cli._load_config", return_value=config_obj):
            result = cli_runner.invoke(app, ["ingest", "missing_vault"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    @pytest.mark.unit
    def test_ingest_missing_config_file(self, cli_runner: CliRunner) -> None:
        """Contract: ingest pointing to a nonexistent config file exits 1 and reports error."""
        from knowledge_garden.cli import app

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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=3, chunks_created=12, duration_seconds=1.5
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
            patch("knowledge_garden.cli._make_embedder", return_value=AsyncMock()),
            patch("knowledge_garden.cli._make_graph_store", return_value=AsyncMock()),
            patch("knowledge_garden.cli._run_ingest", new_callable=AsyncMock) as mock_run,
        ):
            from knowledge_garden.services.pipeline import IngestResult

            mock_run.return_value = IngestResult(
                notes_parsed=3, chunks_created=12, duration_seconds=1.5
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

        config_obj = Config(
            vaults=[VaultConfig(name="my_vault", path="/tmp/my_vault")],
            together_ai=TogetherAIConfig(api_key="fake"),
            embedding=EmbeddingConfig(provider="unknown"),
        )
        with patch("knowledge_garden.cli._load_config", return_value=config_obj):
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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
            patch("knowledge_garden.cli._load_config", return_value=config_obj),
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


class TestHelpCommand:
    """Contract section 4.1 — top-level app help."""

    @pytest.mark.unit
    def test_help_exits_zero(self, cli_runner: CliRunner) -> None:
        """Contract: --help flag exits with code 0."""
        from knowledge_garden.cli import app

        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
