# 13 — Frontmatter Preservation

## What

When a Knowledge Garden ingest reads an Obsidian note that begins with a YAML
frontmatter block (e.g. `---\ntags: [foo]\n---`), the parser must extract that
block into a structured field on the `Note`, store it through Neo4j, and merge
it back into the file the exporter writes.

After this change:
- The original frontmatter is no longer left as raw text inside the note body.
- Embedding chunks are computed from the body alone, not from YAML lines.
- Exported files contain a single, merged YAML frontmatter block at the top
  that combines the user's original keys with the garden-generated keys
  (`title`, `source_vault`, `garden_id`).

## Why

Today the parser stores the entire raw file (including frontmatter) as
`Note.content`. The exporter then prepends its own YAML block, so exported
files end up with two frontmatter regions: a real one at the top and a
duplicated one inside the body. The duplicated YAML also pollutes embedding
chunks, hurting semantic search quality.

This is also the behavior that spec 09 (export) already assumed — its
"Dependencies and assumptions" section claims "Note content stored in Neo4j
has frontmatter already stripped (enforced by `MarkdownParser`)". This spec
makes that claim true.

## Non-goals

- **No automatic backfill.** Notes ingested before this spec will continue to
  store raw content with embedded frontmatter. A re-ingest is required to
  populate `Note.frontmatter` for existing notes. This is documented in the
  contract.
- **No frontmatter schema validation.** Any well-formed YAML mapping is
  accepted as-is.
- **No comment / formatting preservation.** PyYAML's `safe_load` /
  `safe_dump` round-trip discards comments, key order beyond what we control,
  and any quoting style choices. Garden-generated keys take precedence on
  collision (see contract Section 4).
- **No support for non-mapping top-level YAML.** If the YAML at the top of a
  file is a list or non-null scalar (i.e. not a dict and not `None`), it is
  treated as malformed (warning + empty dict, raw content preserved). An
  *empty* frontmatter block (`---\n---\n` or one whose body is whitespace
  only) is treated as an intentional clean strip: `frontmatter={}`, the
  block is removed from content, and no warning is logged.

## Wikilinks inside frontmatter

Wikilink extraction runs on the *raw* file content (before frontmatter
stripping). A wikilink that appears inside a frontmatter value (for example
`related: "[[Foo]]"` or `up: [[Project]]`) therefore continues to produce a
graph edge via `outgoing_links`, exactly as it did before this spec. The
stored `Note.content` still has the frontmatter block stripped.
