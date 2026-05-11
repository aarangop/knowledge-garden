# 09 — Knowledge Export

Amends: 04_ingestion_api (adds export endpoint), 03_cli (adds export command)

## Problem

After ingestion and semantic linking, the graph contains Note nodes connected by both LINKS_TO (explicit wikilinks from the source vaults) and RELATED_TO (discovered via embedding similarity). This data lives entirely inside Neo4j. The user cannot open it in Obsidian, browse it visually, or navigate the discovered connections without querying the database directly.

The final product promised by Knowledge Garden — a unified flat Obsidian vault with cross-vault links surfaced — does not yet exist.

## Desired behavior

Running `kg export` (or `POST /api/v1/export`) reads all Note nodes from the graph and writes one `.md` file per note into `export.output_dir`. Each output file contains:

1. A minimal YAML frontmatter block (`title`, `source_vault`, `garden_id`).
2. The original note content, with its old frontmatter stripped (the parser already strips frontmatter before storing content in Neo4j, so this is a no-op in the current pipeline; the exporter documents the invariant explicitly).
3. A `## References` section with two optional subsections:
   - `### Links` — wikilinks to notes connected by LINKS_TO, sorted alphabetically.
   - `### Discovered Connections` — wikilinks to notes connected by RELATED_TO, sorted by similarity score descending.
   - If a subsection would be empty, it is omitted. If both subsections are empty, the entire `## References` section is omitted.
   - A note that appears in both LINKS_TO and RELATED_TO is listed in both subsections (not deduplicated across subsections).

Filename conflict resolution: if two notes from different vaults share the same title, both output filenames are disambiguated as `{title} ({source_vault}).md`. Wikilinks within the References sections use the resolved output filename title (without the `.md` extension).

The export is idempotent: re-running overwrites existing files. The output directory is created if it does not exist.

## Open questions

None. All design decisions are encoded in this spec.
