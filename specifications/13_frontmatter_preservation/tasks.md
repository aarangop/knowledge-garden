# 13 — Tasks

TDD order. Each phase: red tests → implementation → verify green.

## Phase 1 — `Note` model

- [ ] Add `frontmatter: dict[str, Any]` (default `{}` via
      `default_factory=dict`) to `Note` in `src/knowledge_garden/models/note.py`
- [ ] Verify existing test suite still passes (no test changes needed here;
      field has a default and existing constructors omit it)

## Phase 2 — Parser (red)

- [ ] In `tests/test_parser.py`, add a `TestFrontmatter` class with the
      tests listed in contract Section 6.1. The class must include, at
      minimum, all of:
  - `test_no_frontmatter`
  - `test_simple_frontmatter`
  - `test_frontmatter_no_trailing_newline`
  - `test_frontmatter_crlf`
  - `test_empty_frontmatter_block` — input `"---\n---\nbody"`; assert
    `frontmatter == {}`, `content == "body"` (block stripped), and
    `caplog` records **no** `WARNING` from the parser logger
  - `test_whitespace_only_frontmatter_block` — input
    `"---\n\n---\nbody"`; assert `frontmatter == {}`,
    `content == "body"`, and no warning is logged
  - `test_malformed_yaml` (caplog asserts WARNING)
  - `test_top_level_yaml_list` (caplog asserts WARNING)
  - `test_top_level_yaml_scalar` (caplog asserts WARNING)
  - `test_frontmatter_nested_dict`
  - `test_frontmatter_multiline_string`
  - `test_dashes_not_at_start`
  - `test_wikilink_in_frontmatter_value_extracted` — input
    `"---\nup: \"[[Project]]\"\nrelated: \"[[Foo]]\"\n---\n[[Bar]]\n"`;
    assert `note.frontmatter == {"up": "[[Project]]", "related": "[[Foo]]"}`,
    `note.content == "[[Bar]]\n"` (block stripped), and
    `set(note.outgoing_links) >= {"Project", "Foo", "Bar"}` (wikilinks
    inside the frontmatter still produce graph edges because extraction
    runs on the raw content)
- [ ] Run `uv run pytest tests/test_parser.py -v` — confirm new tests fail

## Phase 2 — Parser (green)

- [ ] Add `FRONTMATTER_RE` constant to `src/knowledge_garden/services/parser.py`
- [ ] Add module-level `logger = logging.getLogger(__name__)`
- [ ] Update `MarkdownParser.parse_file` to follow the algorithm in contract
      Section 2.2:
  1. Read raw file content.
  2. Run `extract_wikilinks` on the **raw** content (not the stripped
     body) so wikilinks inside frontmatter values still populate
     `outgoing_links`.
  3. Match `FRONTMATTER_RE` and branch on `yaml.safe_load` result using
     the three-case rule:
     - `None` → clean strip: `frontmatter={}`, body is `raw[match.end():]`,
       no warning.
     - `dict` → `frontmatter=parsed`, body is `raw[match.end():]`.
     - `YAMLError` raised, or non-`None` non-`dict` value → warning
       logged, `frontmatter={}`, body is `raw` (unchanged).
  4. Construct the `Note` with the stripped `body` as `content`, the
     raw-extracted wikilink lists, and the parsed `frontmatter`.
- [ ] Run `uv run pytest tests/test_parser.py -v` — all green

## Phase 3 — Neo4j store (red)

- [ ] In `tests/test_neo4j_store.py`, add `TestFrontmatterPersistence` class
      with the unit tests listed in contract Section 6.2
- [ ] Add the integration test
      `test_upsert_note_round_trip_preserves_frontmatter` (under the
      `pytest.mark.integration` marker)
- [ ] Run `uv run pytest tests/test_neo4j_store.py -v -m unit` — confirm new
      unit tests fail

## Phase 3 — Neo4j store (green)

- [ ] Import `json` at the top of
      `src/knowledge_garden/services/neo4j_store.py`
- [ ] Update `upsert_note` Cypher and parameters to set
      `n.frontmatter_json = $frontmatter_json` per contract Section 3.2
- [ ] Add static helper `_deserialize_frontmatter(node)` per contract
      Section 3.3
- [ ] Update `get_all_notes` to pass
      `frontmatter=self._deserialize_frontmatter(node)` when constructing
      each `Note`
- [ ] Update `get_note_by_id` likewise
- [ ] Run `uv run pytest tests/test_neo4j_store.py -v -m unit` — all green
- [ ] (Local Neo4j available) Run integration tests — all green

## Phase 4 — Exporter (red)

- [ ] Update the `make_note` fixture in `tests/test_exporter.py` to accept an
      optional `frontmatter` argument (contract Section 6.4)
- [ ] Update existing `test_compose_file_includes_frontmatter` to parse the
      YAML block instead of asserting on the literal string (contract
      Section 6.3)
- [ ] Update any other existing tests that slice on the old fixed
      frontmatter width
- [ ] Add the `TestComposeFileFrontmatterMerge` class with the 7 tests in
      contract Section 6.3
- [ ] Run `uv run pytest tests/test_exporter.py -v` — confirm new tests fail
      and updated existing tests pass against current code only when
      trivially still true (some will fail until phase 4 green)

## Phase 4 — Exporter (green)

- [ ] Import `yaml` at the top of
      `src/knowledge_garden/services/exporter.py`
- [ ] Rewrite `_compose_file` per contract Section 4.1: build `merged` from
      `note.frontmatter` then overlay `title`, `source_vault`, `garden_id`;
      emit via `yaml.safe_dump(merged, default_flow_style=False,
      sort_keys=False, allow_unicode=True)`
- [ ] Wrap with `---\n` and `---\n` fences, then append body and references
      section as before
- [ ] Run `uv run pytest tests/test_exporter.py -v` — all green

## Phase 5 — Verify and lint

- [ ] Run full unit suite: `uv run pytest tests/ -v -m unit` — all green
- [ ] Run `uv run ruff check src/ tests/` — clean
- [ ] Run `uv run mypy src/` — clean
- [ ] (Optional, if Neo4j running) Run `uv run pytest tests/ -v -m
      integration` — all green
