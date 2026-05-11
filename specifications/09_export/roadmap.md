# 09 — Roadmap

## Step 1: Add `get_note_relationships_with_scores` to GraphStore

The exporter needs RELATED_TO scores (for sorting) in addition to the target note IDs already returned by `get_note_relationships`. Extend GraphStore with a new abstract method that returns both LINKS_TO and RELATED_TO targets together with their scores (LINKS_TO score is always 1.0 since no score is stored on those edges).

**Done when:** `get_note_relationships_with_scores(note_id)` returns a dict with keys `LINKS_TO` and `RELATED_TO`, each containing a list of `(target_note_id_str, score)` tuples. Neo4j implementation passes the test suite.

## Step 2: Implement VaultExporter service

Create `services/exporter.py`. The exporter:
- Loads all notes via `get_all_notes()` and builds an in-memory `dict[UUID, Note]` map.
- Detects filename conflicts (notes sharing a title across vaults) and builds a `dict[UUID, str]` mapping each note's UUID to its output filename stem (title or `title (vault)`).
- For each note: fetches its relationships with scores, formats the `## References` section, composes the full output file content, and writes to disk.
- Returns an `ExportResult` dataclass.

**Done when:** `VaultExporter.export()` produces correct markdown files for a set of notes with and without conflicts, with correctly sorted and formatted References sections.

## Step 3: Add `ExportPhase` and progress callback

Define `ExportPhase(StrEnum)` with a single value `WRITING`. The progress callback signature mirrors the pattern from specs 07 and 08.

**Done when:** `export()` fires progress callbacks as files are written.

## Step 4: Add `kg export` CLI command

Add an `export` command to `cli.py` following the same structure as `kg link`. It calls `_run_export`, which creates a `VaultExporter` and runs it with a Rich progress bar. On completion it prints a summary table.

**Done when:** `kg export --config config.yaml` exits 0, displays a progress bar, and prints a result table with `notes_exported`, `files_written`, and `duration`.

## Step 5: Add `POST /api/v1/export` endpoint

Add the `/export` route to `api/routes.py`. The endpoint reads `output_dir` from the request body (overriding the config default if provided), creates a `VaultExporter`, runs it, and returns the result as JSON.

**Done when:** `POST /api/v1/export` returns HTTP 200 with a body containing `notes_exported`, `files_written`, and `output_dir`.
