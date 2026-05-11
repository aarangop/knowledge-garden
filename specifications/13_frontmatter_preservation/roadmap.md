# 13 — Roadmap

Ordered phases. Each phase ends with a working test suite (red → green) for
the items in that phase. Later phases depend on earlier phases.

## Phase 1 — `Note` model field

- Add `frontmatter: dict[str, Any]` (default `{}`) to `Note` in
  `models/note.py`.
- Done when: `Note(...)` constructs with no `frontmatter` arg and
  `note.frontmatter == {}`; passing a dict round-trips.

Rationale: every later phase depends on the model field existing.

## Phase 2 — Parser extraction

- Detect a YAML frontmatter block at the very start of a file.
- Parse with `yaml.safe_load`. On success, store the dict as
  `Note.frontmatter` and strip the block (and its trailing newline) from
  `Note.content`.
- On malformed YAML or non-mapping top-level YAML: log a warning, set
  `frontmatter={}`, leave content unchanged.
- Done when: the new parser unit tests pass and existing parser tests still
  pass.

## Phase 3 — Neo4j persistence

- `upsert_note`: serialize `note.frontmatter` to JSON and write a
  `frontmatter_json` property on the `Note` node.
- `get_all_notes` and `get_note_by_id`: deserialize `frontmatter_json` into
  the reconstructed `Note`. Default to `{}` when the property is missing or
  malformed.
- Done when: the new Neo4j unit tests (mock-based) pass; existing Neo4j tests
  remain green.

## Phase 4 — Exporter merge

- In `_compose_file`, build a single dict by starting from `note.frontmatter`
  and overlaying the garden keys (`title`, `source_vault`, `garden_id`),
  preserving insertion order so user keys appear first.
- Emit a single `---\n...\n---\n` block via `yaml.safe_dump`.
- Done when: the new exporter tests pass; existing exporter tests are
  updated to match the new YAML emission and remain green.

## Phase 5 — Dependencies & lint

- Confirm `pyyaml` is in `[project] dependencies` (it already is).
- Confirm `types-PyYAML` is in dev dependencies (it already is).
- Done when: `uv run mypy src/` and `uv run ruff check src/ tests/` pass.
