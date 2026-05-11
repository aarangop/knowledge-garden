# 13 — Contract

This contract specifies frontmatter preservation across the parser, the
`Note` model, the Neo4j store, and the exporter. It builds on:

- Spec 02 (`MarkdownParser`)
- Spec 01 (`GraphStore`, `Neo4jGraphStore`)
- Spec 09 (`VaultExporter`, `_compose_file`)

The contract is authoritative. Implementations must match it exactly.

---

## 1. `Note` model

File: `src/knowledge_garden/models/note.py`.

Add one field to `Note`:

```python
from typing import Any

class Note(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    content: str
    vault: str
    original_path: str
    outgoing_links: list[str] = []
    attachment_refs: list[str] = []
    resolved_links: list[UUID] = []
    frontmatter: dict[str, Any] = Field(default_factory=dict)
```

Rules:

- Field type: `dict[str, Any]`. Keys are strings (we accept whatever
  `yaml.safe_load` returns; YAML allows non-string keys, but for our usage we
  type-annotate as `str` and rely on `safe_load`).
- Default: empty dict (use `default_factory=dict` to avoid the shared-mutable
  default trap).
- Must be JSON-serializable when reasonable inputs are provided. We do not
  validate this; we let `json.dumps` raise at persistence time if a user
  manages to construct an unserializable value.

No other fields on `Note` change.

---

## 2. Parser

File: `src/knowledge_garden/services/parser.py`.

### 2.1 Frontmatter detection

A file is considered to have a frontmatter block iff:

1. Its raw text begins with the literal three characters `---` followed by
   either `\n` or `\r\n`.
2. After that opening fence, a closing fence line consisting of exactly `---`
   (followed by `\n`, `\r\n`, or end-of-file) appears later in the file.

Detection regex (anchored at start; closing fence must appear at the start
of a line, hence `re.MULTILINE` in addition to `re.DOTALL`):

```python
import re

FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(\r?\n|\Z)",
    re.DOTALL | re.MULTILINE,
)
```

Group 1 is the YAML body (everything between the opening fence's trailing
newline and the closing fence). Group 1 may be the empty string when the
opening and closing fences are on consecutive lines (`---\n---\n`). Group 1
preserves any trailing newline at the end of the YAML body — important for
multi-line string values (`|` block scalars) which require a trailing
newline to round-trip cleanly through `yaml.safe_load`.

The closing `---` is anchored to the start of a line via `^` (with
`re.MULTILINE`) so the body can be empty or contain blank lines without
ambiguity, and so a `---` appearing mid-line in the body is not mistaken
for the closing fence.

If `FRONTMATTER_RE.match(content)` returns `None`, the file has no
frontmatter.

### 2.2 Behavior of `parse_file`

Update `MarkdownParser.parse_file` so that, after reading the file, the
algorithm is:

1. Read raw file content into `raw`.
2. **Extract wikilinks from `raw`** (the original, unstripped content).
   This preserves the existing behavior so that wikilinks appearing inside
   frontmatter values continue to populate `outgoing_links`.
3. Detect and parse the frontmatter block from `raw`.
4. Strip the frontmatter block from `raw` to produce the stored
   `Note.content`.
5. Construct the `Note` with the stripped `content`, the raw-extracted
   `outgoing_links` / `attachment_refs`, and the parsed `frontmatter`.

The frontmatter detection / parsing step branches on three cases:

```python
import logging
import yaml

logger = logging.getLogger(__name__)

raw = file_path.read_text(encoding="utf-8")

# Step 2: wikilink extraction runs on the RAW content, before any stripping.
note_links, attachment_refs = self.extract_wikilinks(raw)

# Steps 3-4: frontmatter detection, parsing, and stripping.
match = FRONTMATTER_RE.match(raw)
if match is None:
    # Case 1: no frontmatter block at all.
    frontmatter: dict[str, Any] = {}
    body = raw
else:
    yaml_body = match.group(1)
    try:
        parsed = yaml.safe_load(yaml_body)
    except yaml.YAMLError as exc:
        # Case 3a: malformed YAML — warn and preserve raw content.
        logger.warning(
            "Malformed YAML frontmatter; ignoring",
            extra={"path": str(file_path), "error": str(exc)},
        )
        frontmatter = {}
        body = raw
    else:
        if parsed is None:
            # Case 2: empty / whitespace-only frontmatter body. This is an
            # intentional clean strip. No warning. Block IS removed from
            # content.
            frontmatter = {}
            body = raw[match.end():]
        elif isinstance(parsed, dict):
            # Normal case: well-formed mapping.
            frontmatter = parsed
            body = raw[match.end():]
        else:
            # Case 3b: top-level YAML is a non-None, non-dict value
            # (list, scalar, etc.). Treat as malformed.
            logger.warning(
                "YAML frontmatter is not a mapping; ignoring",
                extra={"path": str(file_path), "type": type(parsed).__name__},
            )
            frontmatter = {}
            body = raw
```

Construct the `Note` with `content=body`, `frontmatter=frontmatter`, and the
wikilink lists extracted from `raw` in step 2. All other fields keep their
existing semantics from spec 02.

#### 2.2.1 Three-case branching summary

The behavior of the parser depends only on the result of `yaml.safe_load`
applied to the matched body (when a `---`-delimited block is present at the
start of the file):

| Case | Trigger | `frontmatter` | `content` | Warning logged? |
|---|---|---|---|---|
| 1 | No `---` block at start of file | `{}` | unchanged (raw) | no |
| 2 | `---` block whose body is empty or whitespace only (`yaml.safe_load` returns `None`) | `{}` | block stripped | **no** |
| 3a | `yaml.safe_load` raises `YAMLError` | `{}` | unchanged (raw) | yes |
| 3b | `yaml.safe_load` returns a non-`None`, non-`dict` value (list, scalar, etc.) | `{}` | unchanged (raw) | yes |
| Normal | `yaml.safe_load` returns a `dict` | the parsed dict | block stripped | no |

### 2.3 Edge cases (parser)

| Scenario | Expected behavior |
|---|---|
| File with no `---` at all | `frontmatter={}`, `content` unchanged, no warning |
| File starts with `---\n---\n` (empty body) | `yaml.safe_load("")` returns `None` → **clean strip**: `frontmatter={}`, block removed from content, **no warning** |
| File starts with `---\n\n---\n` (whitespace-only body) | `yaml.safe_load("\n")` returns `None` → **clean strip**: `frontmatter={}`, block removed from content, **no warning** |
| File starts with `---\nkey: value\n---\n` then more text | `frontmatter={"key": "value"}`, content is everything after the closing `---\n` |
| File starts with `---\nkey: value\n---` (no trailing newline) | Match still succeeds (regex allows `\Z`); `frontmatter={"key": "value"}`, `content=""` |
| File starts with `---\nkey: value\n---\r\n` | Match succeeds; CRLF handled |
| Frontmatter contains list values (`tags: [a, b]`) | Stored as `{"tags": ["a", "b"]}` |
| Frontmatter contains nested dicts | Stored as nested dict |
| Frontmatter contains multi-line string (`note: \|\n  hello\n  world\n`) | Stored as `{"note": "hello\nworld\n"}` (YAML literal block) |
| Malformed YAML (e.g. `key: : :`) | Warning logged; `frontmatter={}`; raw content preserved |
| Top-level YAML is a list (`- a\n- b`) | Warning logged; `frontmatter={}`; raw content preserved |
| Top-level YAML is a non-null scalar (e.g. `42`) | Warning logged; `frontmatter={}`; raw content preserved |
| `---` appears later in the file but not at the very start | Not treated as frontmatter (regex is anchored with `\A`) |
| Wikilink inside a frontmatter value (e.g. `up: '[[Project]]'` or `related: [[Foo]]`) | Wikilink extraction runs on the raw file content, so the link **does** appear in `outgoing_links`. The frontmatter block itself is still stripped from stored `Note.content`. |

### 2.4 Logging

Use `logger = logging.getLogger(__name__)` at module scope. Warnings include
the file path and a short reason. No exception is raised for malformed input.

---

## 3. Neo4j store

File: `src/knowledge_garden/services/neo4j_store.py`.

### 3.1 Property name and serialization

Store frontmatter on the `Note` node as a single string property named
`frontmatter_json`, produced by `json.dumps(note.frontmatter,
ensure_ascii=False, sort_keys=False)`.

Empty dict serializes to `"{}"`. Always write the property; never write
`null`.

### 3.2 `upsert_note`

Update the Cypher to set `n.frontmatter_json`:

```python
import json

async def upsert_note(self, note: Note) -> None:
    async with self._driver.session(database=self._database) as session:
        await session.run(
            "MERGE (n:Note {id: $id}) "
            "SET n.title = $title, n.content = $content, "
            "n.vault = $vault, n.original_path = $original_path, "
            "n.frontmatter_json = $frontmatter_json",
            id=str(note.id),
            title=note.title,
            content=note.content,
            vault=note.vault,
            original_path=note.original_path,
            frontmatter_json=json.dumps(
                note.frontmatter, ensure_ascii=False, sort_keys=False
            ),
        )
```

### 3.3 `get_all_notes` and `get_note_by_id`

Add a private helper to deserialize:

```python
@staticmethod
def _deserialize_frontmatter(node: dict) -> dict[str, Any]:
    raw = node.get("frontmatter_json")
    if raw is None:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Malformed frontmatter_json on Note; defaulting to empty dict",
            extra={"note_id": node.get("id")},
        )
        return {}
    if not isinstance(value, dict):
        return {}
    return value
```

Both `get_all_notes` and `get_note_by_id` must pass
`frontmatter=self._deserialize_frontmatter(node)` when constructing the
`Note`.

### 3.4 No backfill

Notes already in Neo4j without a `frontmatter_json` property continue to
work: the deserialization helper returns `{}`. They will only gain a real
frontmatter on the next ingest.

### 3.5 Other methods

`upsert_chunk`, `find_similar_chunks`, `get_chunks_for_note`,
`get_all_chunks`, `derive_related_to`, `get_stats`, `search_notes`,
`get_note_relationships`, `get_note_relationships_with_scores`,
`create_link`, `create_similarity`: unchanged.

---

## 4. Exporter

File: `src/knowledge_garden/services/exporter.py`.

### 4.1 `_compose_file` rewrite

Replace the hand-built frontmatter string with a merged-and-dumped YAML
block:

```python
import yaml

@staticmethod
def _compose_file(note: Note, stem: str, references_section: str) -> str:
    merged: dict[str, Any] = dict(note.frontmatter)
    # Garden keys overwrite any user keys with the same name.
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
```

### 4.2 Merge precedence

- `note.frontmatter` keys are inserted first into `merged`, preserving the
  user's original key order (Python `dict` retains insertion order; PyYAML's
  `safe_load` of a mapping also preserves order).
- The garden keys `title`, `source_vault`, `garden_id` are then assigned. If
  the user's frontmatter contained any of those keys, the garden values
  overwrite them. The garden keys end up in the user's original positions
  if the user already had them; otherwise they are appended at the end.

This precedence rule is intentional: the garden's identity keys are the
canonical truth for the exported vault. Document loss of a user-supplied
`title` is acceptable because the exported `title` reflects the
disambiguated stem.

### 4.3 YAML emission

`yaml.safe_dump(merged, default_flow_style=False, sort_keys=False,
allow_unicode=True)` always returns a string ending in `\n`. The output
frontmatter is therefore always exactly:

```
---
<yaml_block_lines>
---
```

followed by a `\n` (after `---`). One blank line then separates the closing
fence from the body. The body and references sections are unchanged from
spec 09.

### 4.4 Edge cases (exporter)

| Scenario | Expected behavior |
|---|---|
| `note.frontmatter == {}` | Output frontmatter contains only `title`, `source_vault`, `garden_id` (in that order) |
| User `frontmatter == {"tags": ["a", "b"]}` | YAML block contains `tags:\n- a\n- b\n` followed by garden keys |
| User `frontmatter == {"title": "User's title"}` | Garden's `title` (the stem) wins; user's title is silently dropped |
| User key with non-ASCII (e.g. `"summary": "café"`) | `allow_unicode=True` keeps the raw character (no `\xNN` escape) |
| User key whose value is a nested dict | Emitted as block-style nested YAML |
| Garden-only output is well-formed YAML | Always: `safe_dump` quotes keys/values as needed |

---

## 5. Dependencies

`pyyaml>=6.0.0` is already in `[project] dependencies`. No change required.

`types-pyyaml` is already in dev dependencies. No change required.

The executor must import `yaml` and `json` where used. No new third-party
packages are introduced by this spec.

---

## 6. Test specifications

All tests in this section use the `pytest.mark.unit` marker unless stated
otherwise. New tests live in existing test files where appropriate.

### 6.1 `tests/test_parser.py` — new class `TestFrontmatter`

Fixtures: existing `sample_vault_config` and `tmp_path`.

| Test | Input file content | Expected `note.frontmatter` | Expected `note.content` |
|---|---|---|---|
| `test_no_frontmatter` | `"# Hello\nWorld"` | `{}` | `"# Hello\nWorld"` |
| `test_simple_frontmatter` | `"---\ntitle: Foo\ntags: [a, b]\n---\n# Body\n"` | `{"title": "Foo", "tags": ["a", "b"]}` | `"# Body\n"` |
| `test_frontmatter_no_trailing_newline` | `"---\nkey: value\n---"` | `{"key": "value"}` | `""` |
| `test_frontmatter_crlf` | `"---\r\nkey: value\r\n---\r\nbody"` | `{"key": "value"}` | `"body"` |
| `test_empty_frontmatter_block` | `"---\n---\nbody"` | `{}` (clean strip; **no warning**) | `"body"` (block removed) |
| `test_whitespace_only_frontmatter_block` | `"---\n\n---\nbody"` | `{}` (clean strip; **no warning**) | `"body"` (block removed) |
| `test_malformed_yaml` | `"---\nkey: : :\n---\nbody"` | `{}` (warning logged) | `"---\nkey: : :\n---\nbody"` (raw preserved) |
| `test_top_level_yaml_list` | `"---\n- a\n- b\n---\nbody"` | `{}` (warning logged) | raw preserved |
| `test_top_level_yaml_scalar` | `"---\n42\n---\nbody"` | `{}` (warning logged) | raw preserved |
| `test_frontmatter_nested_dict` | `"---\nmeta:\n  k: v\n---\nbody"` | `{"meta": {"k": "v"}}` | `"body"` |
| `test_frontmatter_multiline_string` | `"---\nnote: \|\n  a\n  b\n---\nbody"` | `{"note": "a\nb\n"}` | `"body"` |
| `test_dashes_not_at_start` | `"hello\n---\nkey: v\n---\n"` | `{}` | unchanged |
| `test_wikilink_in_frontmatter_value_extracted` | `"---\nup: \"[[Project]]\"\nrelated: \"[[Foo]]\"\n---\n[[Bar]]\n"` | `{"up": "[[Project]]", "related": "[[Foo]]"}` | `note.content == "[[Bar]]\n"`; `note.outgoing_links` contains all of `"Project"`, `"Foo"`, `"Bar"` (wikilinks are extracted from the raw file content, before stripping) |

Edge-case verification:
- `test_malformed_yaml`, `test_top_level_yaml_list`, and
  `test_top_level_yaml_scalar` must use `caplog` to assert a `WARNING`
  record was emitted with the file path in the message or `extra`.
- `test_empty_frontmatter_block` and
  `test_whitespace_only_frontmatter_block` must use `caplog` to assert
  that **no** `WARNING` record was emitted by the parser logger during the
  call.

### 6.2 `tests/test_neo4j_store.py` — new class `TestFrontmatterPersistence`

These are unit tests using `AsyncMock` patches of the driver session
(matching the existing patching style at the top of the file). No live
Neo4j required.

| Test | Setup | Assertion |
|---|---|---|
| `test_upsert_note_writes_frontmatter_json` | `Note(frontmatter={"tags": ["a"]})` | The Cypher call's parameters include `frontmatter_json='{"tags": ["a"]}'` |
| `test_upsert_note_empty_frontmatter_serializes_to_empty_object` | `Note(frontmatter={})` | parameters include `frontmatter_json="{}"` |
| `test_upsert_note_unicode_frontmatter_no_ascii_escape` | `Note(frontmatter={"summary": "café"})` | parameters' `frontmatter_json` contains the literal `"café"` (no `é`) |
| `test_get_all_notes_deserializes_frontmatter_json` | mock returns one node with `frontmatter_json='{"tags": ["a"]}'` | returned `Note.frontmatter == {"tags": ["a"]}` |
| `test_get_all_notes_missing_property_defaults_to_empty` | mock returns a node with no `frontmatter_json` key | returned `Note.frontmatter == {}` |
| `test_get_all_notes_malformed_json_defaults_to_empty` | mock returns `frontmatter_json="not-json"` | returned `Note.frontmatter == {}`; warning logged |
| `test_get_all_notes_non_dict_json_defaults_to_empty` | mock returns `frontmatter_json="[1,2,3]"` | returned `Note.frontmatter == {}` |
| `test_get_note_by_id_deserializes_frontmatter_json` | mock returns one node with `frontmatter_json='{"k":"v"}'` | returned `Note.frontmatter == {"k": "v"}` |
| `test_get_note_by_id_missing_property_defaults_to_empty` | node without `frontmatter_json` | `Note.frontmatter == {}` |

Existing integration tests in `TestNeo4jStoreUpsertNote` continue to use
notes with default (empty) frontmatter and are unaffected. One new
integration test is added:

| Test (integration) | Setup | Assertion |
|---|---|---|
| `test_upsert_note_round_trip_preserves_frontmatter` | upsert a Note with `frontmatter={"tags": ["a", "b"], "meta": {"k": "v"}}`; call `get_note_by_id` | returned note's `frontmatter` equals the input dict |

### 6.3 `tests/test_exporter.py` — updated and new tests

The existing `make_note` factory must accept an optional
`frontmatter: dict[str, Any] | None = None` argument; when `None`, default
to `{}`.

Update existing tests that assert on the literal frontmatter format:

- `test_compose_file_includes_frontmatter` — Update the assertion from a
  hand-built string to: parse the leading `---\n...\n---\n` block with
  `yaml.safe_load` and assert the resulting dict equals
  `{"title": stem, "source_vault": note.vault, "garden_id": str(note.id)}`.
- `test_compose_file_ends_with_newline` — unchanged.
- `test_compose_file_includes_content`, `test_compose_file_with_references`,
  `test_compose_file_no_references` — unchanged in intent, but update any
  string slicing that assumed the old fixed-width frontmatter to instead
  split on the second `---\n` line.

Add the following new tests under a class `TestComposeFileFrontmatterMerge`:

| Test | Input | Expected behavior |
|---|---|---|
| `test_compose_file_merges_user_frontmatter` | `note.frontmatter={"tags": ["a", "b"]}`, `stem="My Note"` | parsed frontmatter equals `{"tags": ["a", "b"], "title": "My Note", "source_vault": <vault>, "garden_id": <id>}`; user keys come first (assert `list(parsed.keys())[0] == "tags"`) |
| `test_compose_file_garden_keys_override_user_keys` | `note.frontmatter={"title": "User Title", "garden_id": "fake"}` | parsed `title == stem` and parsed `garden_id == str(note.id)` (user values overridden) |
| `test_compose_file_no_user_frontmatter` | `note.frontmatter={}` | parsed frontmatter has exactly three keys: `title`, `source_vault`, `garden_id` |
| `test_compose_file_unicode_frontmatter` | `note.frontmatter={"summary": "café"}` | the frontmatter block, sliced as text, contains the literal substring `café` (no `é` escape) |
| `test_compose_file_nested_user_frontmatter` | `note.frontmatter={"meta": {"k": "v"}}` | parsing the YAML block round-trips to `meta == {"k": "v"}` |
| `test_compose_file_single_frontmatter_block` | any note | the output text contains exactly two lines that match `^---\s*$` (count via `len([l for l in lines if l.strip() == "---"]) == 2`) |
| `test_compose_file_user_keys_appear_before_garden_keys` | `note.frontmatter={"a": 1, "b": 2}`, no key collisions | parsed key order is `["a", "b", "title", "source_vault", "garden_id"]` |

### 6.4 `tests/test_exporter.py` — `make_note` fixture update

The fixture is updated as follows:

```python
@pytest.fixture
def make_note():
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
```

All other test files that import `Note` directly continue to construct it
without `frontmatter` (the field defaults to `{}`).

### 6.5 `tests/test_pipeline.py` — no changes required

The pipeline (spec 06/07) calls `parser.parse_file` and forwards the
resulting `Note` to `graph_store.upsert_note`. Both ends of that handoff are
covered by the parser and Neo4j tests above; no integration-level test is
added.

---

## 7. Edge cases summary

| Layer | Edge case | Outcome |
|---|---|---|
| Parser | No frontmatter | `frontmatter={}`, content unchanged, no warning |
| Parser | Empty / whitespace-only frontmatter block (`---\n---\n`) | Clean strip: `frontmatter={}`, block removed from content, **no warning** |
| Parser | Malformed YAML | Warning logged; `frontmatter={}`; raw content preserved |
| Parser | Top-level YAML is list / non-null scalar | Warning logged; `frontmatter={}`; raw content preserved |
| Parser | Frontmatter without trailing newline (file ends at `---`) | Parsed; body becomes `""` |
| Parser | CRLF line endings | Parsed; works identically to LF |
| Parser | Wikilink inside a frontmatter value | Extracted into `outgoing_links` (wikilink extraction runs on raw content); frontmatter block still stripped from stored content |
| Neo4j | Property absent on legacy node | `frontmatter` defaults to `{}` |
| Neo4j | Property is non-JSON string | Warning logged; `frontmatter` defaults to `{}` |
| Neo4j | Property holds a JSON list / scalar | `frontmatter` defaults to `{}` |
| Exporter | Empty user frontmatter | Output frontmatter has 3 garden keys only |
| Exporter | User key collides with garden key | Garden value wins; user value silently dropped |
| Exporter | Unicode value | Preserved verbatim (`allow_unicode=True`) |
| Exporter | Nested dict / list value | Round-trips through YAML |

---

## 8. Dependencies and assumptions

- Builds on spec 02 (`MarkdownParser.parse_file` signature). The signature
  is unchanged.
- Builds on spec 01 (`Neo4jGraphStore.upsert_note`, `get_all_notes`,
  `get_note_by_id`). Only the Cypher and reconstruction step change; the
  method signatures are unchanged.
- Builds on spec 09 (`VaultExporter._compose_file`). Signature is
  unchanged; the output bytes change.
- `pyyaml>=6.0.0` is in dependencies.
- `types-pyyaml` is in dev dependencies.
- No backfill is performed: existing Neo4j nodes without `frontmatter_json`
  continue to load with `frontmatter={}`. Re-ingestion is the documented
  path to populate them.
