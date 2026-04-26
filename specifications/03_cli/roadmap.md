# Roadmap: CLI and Pipeline Extraction

Steps are ordered by dependency. Each step can be implemented and verified independently before the next begins.

---

## Step 1 — Add runtime dependencies

**Files:** `pyproject.toml`

**Description:** Add `typer` and `rich` as runtime dependencies. These are needed by the CLI module introduced in Step 4.

**Done when:**
- `pyproject.toml` lists `typer>=0.12.0` and `rich>=13.0.0` in `[project] dependencies`.
- `uv sync` completes without error.
- `python -c "import typer, rich"` exits 0.

---

## Step 2 — Extract IngestPipeline service

**File:** `src/knowledge_garden/services/pipeline.py`

**Description:** Move the ingest orchestration logic out of `routes.py` and into a dedicated `IngestPipeline` class. The class takes explicit dependencies at construction time and runs parse → chunk → embed → upsert when called.

**Done when:**
- `IngestPipeline` exists in `src/knowledge_garden/services/pipeline.py`.
- It accepts `MarkdownParser`, `NoteChunker`, `EmbeddingService`, and `GraphStore` in its constructor.
- `run(vault_config, progress_callback)` executes the full pipeline and returns an `IngestResult` dataclass with `notes_parsed`, `chunks_created`, and `duration_seconds`.
- The optional `progress_callback` is called once per note with `(current_index: int, total: int, note_title: str)`.
- All unit tests in `tests/test_pipeline.py` pass.

---

## Step 3 — Remove ingest endpoint from the API

**Files:** `src/knowledge_garden/api/routes.py`, `tests/test_ingest_api.py`

**Description:** Delete the `POST /api/v1/ingest` handler and its Pydantic schemas (`IngestRequest`, `IngestResponse`) from `routes.py`. Delete `tests/test_ingest_api.py` in full. The `GET /api/v1/notes` handler and its schemas (`NoteSummary`, `NotesListResponse`) are not touched.

**Done when:**
- `routes.py` no longer imports or references `MarkdownParser`, `NoteChunker`, `IngestRequest`, or `IngestResponse`.
- `routes.py` no longer has `@router.post("/ingest")`.
- `tests/test_ingest_api.py` does not exist.
- `uv run pytest tests/ -v -m unit` passes (no reference to the deleted file).
- `GET /api/v1/notes` tests in `tests/test_notes_api.py` still pass.

---

## Step 4 — Implement CLI entry point

**File:** `src/knowledge_garden/cli.py`

**Description:** Implement the three CLI commands using `typer` and `rich`. Each command loads `Config.from_yaml("config.yaml")`, instantiates services, and delegates to `IngestPipeline` or `GraphStore` as appropriate.

**Done when:**
- `kg ingest <vault_name>` is implemented and prints a progress bar per note and a summary table on completion.
- `kg notes [--vault <name>]` is implemented and prints a `rich.table.Table` of all notes, optionally filtered.
- `kg status` is implemented and prints aggregate note/chunk counts grouped by vault.
- All unit tests in `tests/test_cli.py` pass.

---

## Step 5 — Register `kg` entry point in pyproject.toml

**File:** `pyproject.toml`

**Description:** Add a `[project.scripts]` table pointing `kg` at `knowledge_garden.cli:app`.

**Done when:**
- `pyproject.toml` contains:
  ```toml
  [project.scripts]
  kg = "knowledge_garden.cli:app"
  ```
- After `uv sync`, running `kg --help` prints the top-level command list without error.

---

## Step 6 — Final verification

**Description:** Confirm the full test suite passes, linting and type-checking are clean, and the `kg` command works end-to-end against a real config.

**Done when:**
- `uv run pytest tests/ -v -m unit` passes all unit tests.
- `uv run ruff check src/ tests/` exits 0.
- `uv run mypy src/` exits 0.
- `kg --help` prints usage.
- `kg ingest <vault_name>` runs against a local vault (manual smoke test).
