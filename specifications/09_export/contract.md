# 09 — Contract

## 1. GraphStore extension: `get_note_relationships_with_scores`

New abstract method on `GraphStore` (in `services/graph_store.py`):

```python
@abstractmethod
async def get_note_relationships_with_scores(
    self, note_id: object
) -> dict[str, list[tuple[str, float]]]:
    """Return LINKS_TO and RELATED_TO targets for a Note, each with a score.

    Returns a dict with up to two keys:
      "LINKS_TO"   -> list of (target_note_id_str, 1.0)   (score always 1.0)
      "RELATED_TO" -> list of (target_note_id_str, score)  (score from r.score on edge)

    A key is absent if there are no relationships of that type.
    """
    ...
```

Neo4j implementation (in `services/neo4j_store.py`):

```cypher
MATCH (n:Note {id: $id})-[r:LINKS_TO|RELATED_TO]->(m:Note)
RETURN type(r) AS rel_type, m.id AS target_id,
       CASE type(r) WHEN 'RELATED_TO' THEN r.score ELSE 1.0 END AS score
```

Return type: `dict[str, list[tuple[str, float]]]`. Build with `setdefault`.

Implementation note: the existing `get_note_relationships` method is unchanged. The new method is additive.

## 2. ExportResult dataclass

New dataclass in `services/exporter.py`:

```python
from dataclasses import dataclass

@dataclass
class ExportResult:
    notes_exported: int      # total Note nodes processed
    files_written: int       # actual files written (may equal notes_exported)
    duration_seconds: float
```

`files_written` equals `notes_exported` in all current cases (one file per note, conflicts resolved by renaming — no note is dropped).

## 3. ExportPhase StrEnum

```python
from enum import StrEnum

class ExportPhase(StrEnum):
    WRITING = "writing"
```

Progress callback type:

```python
from collections.abc import Callable

ExportProgressCallback = Callable[[ExportPhase, int, int, str], None]
```

Signature: `(phase, current, total, detail_str)`. Fired once per file written.

## 4. VaultExporter service

New class in `services/exporter.py`:

```python
class VaultExporter:
    def __init__(
        self,
        graph_store: GraphStore,
        output_dir: str | Path,
    ) -> None:
        """
        Args:
            graph_store: Graph storage backend (abstract interface from spec 01).
            output_dir: Destination directory for exported markdown files.
                        Created if it does not exist.
        """
```

### `export`

```python
async def export(
    self,
    progress_callback: ExportProgressCallback | None = None,
) -> ExportResult:
    """Export all notes from the graph to markdown files in output_dir.

    Algorithm:
    1. Call graph_store.get_all_notes() → list[Note].
    2. Build conflict map: group notes by title (case-sensitive).
       Any title group with more than one note is flagged as conflicted.
    3. Build output stem map: dict[UUID, str].
       - Non-conflicted note: stem = note.title
       - Conflicted note: stem = f"{note.title} ({note.vault})"
    4. Ensure output_dir exists (mkdir parents=True, exist_ok=True).
    5. For each note (order: sorted by stem for determinism):
       a. Fetch relationships: graph_store.get_note_relationships_with_scores(note.id)
       b. Resolve target UUIDs to output stems using the stem map
          (skip targets whose UUIDs are not in the map — orphaned edges).
       c. Build the ## References section via _build_references_section().
       d. Compose file content via _compose_file().
       e. Write to output_dir / f"{stem}.md" (overwrite if exists).
       f. Fire progress_callback(ExportPhase.WRITING, idx+1, total, stem).
    6. Return ExportResult(notes_exported=total, files_written=total,
                           duration_seconds=elapsed).

    Returns:
        ExportResult with notes_exported, files_written, duration_seconds.
    """
```

### `_build_conflict_map`

```python
@staticmethod
def _build_conflict_map(notes: list[Note]) -> dict[str, list[Note]]:
    """Group notes by title. Keys with more than one note are conflicts.

    Returns:
        dict mapping title -> list[Note]. All titles included, not only conflicts.
    """
```

### `_build_stem_map`

```python
@staticmethod
def _build_stem_map(notes: list[Note]) -> dict[UUID, str]:
    """Map each note UUID to its output filename stem (no .md extension).

    Non-conflicted note: stem = note.title
    Conflicted note:     stem = f"{note.title} ({note.vault})"

    Args:
        notes: All notes to export.

    Returns:
        dict[UUID, str] — one entry per note.
    """
```

### `_build_references_section`

```python
@staticmethod
def _build_references_section(
    links_to: list[str],         # output stems, already sorted alphabetically
    related_to: list[str],       # output stems, already sorted by score desc
) -> str:
    """Build the ## References markdown block.

    Format when both sections present:

        ## References

        ### Links
        - [[Stem A]]
        - [[Stem B]]

        ### Discovered Connections
        - [[Stem C]]
        - [[Stem D]]

    Rules:
    - If links_to is empty, omit the ### Links subsection entirely.
    - If related_to is empty, omit the ### Discovered Connections subsection entirely.
    - If both are empty, return "" (empty string — no References section written).
    - A trailing newline is included in the returned string when non-empty.

    Args:
        links_to: Pre-sorted list of output filename stems for LINKS_TO targets.
        related_to: Pre-sorted list of output filename stems for RELATED_TO targets.

    Returns:
        Formatted markdown string, or "" if both lists are empty.
    """
```

### `_compose_file`

```python
@staticmethod
def _compose_file(note: Note, stem: str, references_section: str) -> str:
    """Compose the full output markdown file content for a note.

    Format:

        ---
        title: "{stem}"
        source_vault: "{note.vault}"
        garden_id: "{note.id}"
        ---

        {note.content}

        {references_section}

    Rules:
    - The frontmatter title uses the output stem (not note.title), so conflicted
      notes carry the disambiguated title in their own frontmatter.
    - note.content is written as-is (the parser already strips frontmatter before
      storing in Neo4j; the exporter does not strip content again).
    - If references_section is "", it is not appended (no trailing blank section).
    - One blank line separates the closing frontmatter fence from the content.
    - One blank line separates the content from the references section when present.

    Args:
        note: The Note domain model (id, content, vault, etc.).
        stem: The resolved output filename stem for this note.
        references_section: Result of _build_references_section(), may be "".

    Returns:
        Complete file content string, ending with a single newline.
    """
```

## 5. CLI: `kg export` command

New command in `cli.py`:

```python
@app.command()
def export(
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None:
```

Internal coroutine:

```python
async def _run_export(
    graph_store: GraphStore,
    output_dir: str,
) -> ExportResult:
    await graph_store.initialize()
    try:
        exporter = VaultExporter(graph_store, output_dir)
        with Progress(...) as progress:
            writing_task = progress.add_task("Exporting notes...", total=None)

            def progress_callback(
                phase: ExportPhase, current: int, total: int, detail: str
            ) -> None:
                if phase == ExportPhase.WRITING:
                    progress.update(writing_task, total=total, completed=current,
                                    description=f"Writing — {detail}")

            return await exporter.export(progress_callback=progress_callback)
    finally:
        await graph_store.close()
```

The `export` command:
1. Loads `AppSettings` and `BusinessConfig` (same error handling as `link`).
2. Creates `graph_store` via `_make_graph_store`.
3. Runs `asyncio.run(_run_export(graph_store, business.export.output_dir))`.
4. Prints a Rich `Table` with rows:
   - `"Notes exported"` / `result.notes_exported`
   - `"Files written"` / `result.files_written`
   - `"Output dir"` / the resolved output_dir
   - `"Duration"` / `f"{result.duration_seconds:.2f}s"`

Exit code 0 on success. Exit code 1 on `AppSettings` error or missing config file (same pattern as `link`).

## 6. API: `POST /api/v1/export`

New endpoint in `api/routes.py`:

### Request schema

```python
class ExportRequest(BaseModel):
    output_dir: str | None = None  # if None, use app.state.export_output_dir
```

### Response schema

```python
class ExportResponse(BaseModel):
    notes_exported: int
    files_written: int
    output_dir: str
```

### Handler

```python
@router.post("/export")
async def export_vault(body: ExportRequest, request: Request) -> ExportResponse:
    from knowledge_garden.services.exporter import VaultExporter

    graph_store = request.app.state.graph_store
    output_dir = body.output_dir or getattr(request.app.state, "export_output_dir", "./output")
    exporter = VaultExporter(graph_store, output_dir)
    result = await exporter.export()
    return ExportResponse(
        notes_exported=result.notes_exported,
        files_written=result.files_written,
        output_dir=str(output_dir),
    )
```

`app.state.export_output_dir` is set during the FastAPI lifespan from `AppSettings` (or a hardcoded default `"./output"` if not present; details are left to the executor since `AppSettings` does not currently carry an export path).

Error cases:
- If `graph_store` is unavailable: HTTP 503 (pre-existing lifespan error).
- No other error cases unique to this endpoint.

## 7. Configuration

`ExportConfig` already exists in `config.py`:

```python
class ExportConfig(BaseModel):
    output_dir: str = "./output"
```

No changes to `ExportConfig` or `BusinessConfig` are needed. This spec reads the existing field; no new fields are added.

## 8. Test specifications

### Unit tests — `tests/test_exporter.py`

All tests use `pytest.mark.unit`. No Neo4j or filesystem interaction (tmp_path is the only I/O).

**Fixtures needed:**
- `make_note(title, vault, content, note_id)` — factory function returning a `Note`.
- `mock_graph_store` — `AsyncMock(spec=GraphStore)` with `get_all_notes` and `get_note_relationships_with_scores` pre-configured.

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_build_stem_map_no_conflicts` | 2 notes with distinct titles `"A"` (vault `"v1"`) and `"B"` (vault `"v1"`) | `{A.id: "A", B.id: "B"}` |
| `test_build_stem_map_conflict_same_title_different_vaults` | 2 notes both titled `"Note"`, vaults `"v1"` and `"v2"` | `{n1.id: "Note (v1)", n2.id: "Note (v2)"}` |
| `test_build_stem_map_conflict_three_notes_same_title` | 3 notes all titled `"Note"`, vaults `"v1"`, `"v2"`, `"v3"` | all three get `"Note (vX)"` suffixes |
| `test_build_stem_map_single_note` | 1 note | stem equals note.title |
| `test_build_references_both_present` | `links_to=["A", "B"]`, `related_to=["C"]` | string contains `### Links`, `### Discovered Connections`, `[[A]]`, `[[B]]`, `[[C]]` |
| `test_build_references_links_only` | `links_to=["A"]`, `related_to=[]` | contains `### Links`, does NOT contain `### Discovered Connections` |
| `test_build_references_related_only` | `links_to=[]`, `related_to=["C"]` | contains `### Discovered Connections`, does NOT contain `### Links` |
| `test_build_references_both_empty` | `links_to=[]`, `related_to=[]` | returns `""` |
| `test_build_references_links_alphabetical` | `links_to=["Zebra", "Apple", "Mango"]` | output order is `Apple`, `Mango`, `Zebra` — caller is responsible for sorting; test verifies that when caller sorts alphabetically the output matches |
| `test_build_references_related_score_order` | `related_to=["Low", "High"]` (caller passes pre-sorted desc) | output order is `High`, `Low` |
| `test_compose_file_includes_frontmatter` | note with `title="My Note"`, vault `"v1"`, `garden_id=<uuid>` | output starts with `---\ntitle: "My Note"\nsource_vault: "v1"\ngarden_id: "<uuid>"\n---` |
| `test_compose_file_includes_content` | note.content `"Hello world"` | output contains `Hello world` |
| `test_compose_file_with_references` | references_section `"## References\n..."` | output contains the references block |
| `test_compose_file_no_references` | references_section `""` | output does NOT contain `## References` |
| `test_compose_file_ends_with_newline` | any note | last character of output is `\n` |
| `test_export_writes_files` | mock `get_all_notes` returns 2 notes, `get_note_relationships_with_scores` returns `{}` | 2 files created in `tmp_path`, ExportResult.files_written == 2 |
| `test_export_creates_output_dir` | output_dir is a non-existent subdirectory of tmp_path | directory is created during export |
| `test_export_conflict_resolution_filename` | 2 notes both titled `"Note"`, vaults `"v1"` and `"v2"` | files `"Note (v1).md"` and `"Note (v2).md"` exist in output_dir |
| `test_export_references_links_to_alphabetical` | note A has LINKS_TO to notes `["Zebra", "Apple"]` | `### Links` section lists `Apple` before `Zebra` |
| `test_export_references_related_to_score_desc` | note A has RELATED_TO to `[("note_b_id", 0.9), ("note_c_id", 0.7)]` | `### Discovered Connections` lists note_b before note_c |
| `test_export_skips_orphaned_targets` | note A has RELATED_TO to a UUID not in `get_all_notes` result | that target is silently skipped; no KeyError |
| `test_export_idempotent_overwrites` | export run twice to same tmp_path | second run succeeds, same files present |
| `test_export_progress_callback_called` | mock progress_callback | callback called once per note with `ExportPhase.WRITING` |
| `test_export_result_shape` | 3 notes | ExportResult has `notes_exported==3`, `files_written==3`, `duration_seconds >= 0` |
| `test_export_empty_graph` | `get_all_notes` returns `[]` | ExportResult(notes_exported=0, files_written=0, duration_seconds>=0); no files written |

### Unit tests — `tests/test_graph_store.py` (additions)

| Test | Input | Expected output |
|------|-------|-----------------|
| `test_get_note_relationships_with_scores_returns_links_to` | mock session returns one LINKS_TO row | `{"LINKS_TO": [(target_id_str, 1.0)]}` |
| `test_get_note_relationships_with_scores_returns_related_to` | mock session returns one RELATED_TO row with score 0.85 | `{"RELATED_TO": [(target_id_str, 0.85)]}` |
| `test_get_note_relationships_with_scores_both_types` | mock session returns one LINKS_TO and one RELATED_TO row | both keys present in result |
| `test_get_note_relationships_with_scores_empty` | mock session returns no rows | `{}` |

### Unit tests — `tests/test_cli.py` (additions, class `TestExportCommand`)

| Test | Description |
|------|-------------|
| `test_export_command_exits_zero` | Patch `_run_export` as `AsyncMock` returning a valid `ExportResult`; invoke `kg export --config <path>` → exit code 0 |
| `test_export_command_prints_table` | Same patch; output contains `"Notes exported"` and the notes count |
| `test_export_command_config_not_found` | Patch `_load_business_config` to raise `FileNotFoundError` → exit code 1 |
| `test_export_command_settings_error` | Patch `_load_app_settings` to raise `Exception` → exit code 1 |

### Unit tests — `tests/test_notes_api.py` (additions, class `TestExportEndpoint`)

| Test | Description |
|------|-------------|
| `test_export_endpoint_returns_200` | Mock `graph_store.get_all_notes` + `get_note_relationships_with_scores`; `POST /api/v1/export` with `{}` body → HTTP 200 |
| `test_export_endpoint_response_schema` | Response JSON contains keys `notes_exported`, `files_written`, `output_dir` |
| `test_export_endpoint_custom_output_dir` | Body `{"output_dir": "/tmp/custom"}` → `output_dir` in response is `"/tmp/custom"` |

### Integration test — `tests/test_exporter.py`

```
test_exporter_integration_end_to_end
```

Marked `pytest.mark.integration`. Requires live Neo4j.

Steps:
1. Ingest 2 notes (note A with a LINKS_TO to note B).
2. Run `derive_related_to` to create a RELATED_TO edge.
3. Instantiate `VaultExporter` pointing at a `tmp_path` output dir.
4. Call `await exporter.export()`.
5. Assert: 2 files exist in `tmp_path`.
6. Assert: Note A's file contains `### Links` with `[[Note B]]`.

## 9. Edge cases

- Note with no LINKS_TO and no RELATED_TO: file is written with no `## References` section.
- Two notes from the same vault with the same title: this should not occur if dedup (spec 07) ran correctly, but the conflict resolution still fires for them (same vault, same title → both get `{title} ({vault})` — the second write overwrites the first). This is a known limitation documented here; spec 07 is expected to prevent this.
- RELATED_TO edge where `r.score` is NULL (edge created without score): Neo4j `ELSE 1.0` in the Cypher fallback covers this case for the query; the returned score will be `1.0`.
- Note content is empty string: file is still written with frontmatter only (no content body, no blank line before the references section if present).
- Output filesystem is not writable: `PermissionError` propagates to the caller uncaught; no special handling in `VaultExporter`.

## 10. Dependencies and assumptions

- `get_all_notes()` is implemented and tested (spec 01, confirmed in `neo4j_store.py`).
- `RELATED_TO` edges carry an `r.score` float property (set by `derive_related_to` from spec 08).
- Note content stored in Neo4j has frontmatter already stripped (enforced by `MarkdownParser` from spec 02).
- `ExportConfig.output_dir` exists on `BusinessConfig` (confirmed in `config.py`).
- `LinkingConfig` and `DedupConfig` are unchanged from specs 07 and 08.
- The `GraphStore` ABC is in `services/graph_store.py`; the Neo4j implementation is in `services/neo4j_store.py` (both confirmed by reading the files).
