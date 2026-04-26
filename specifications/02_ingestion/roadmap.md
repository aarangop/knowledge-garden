# Roadmap: Vault Ingestion

Steps are ordered by dependency. Each step can be implemented and verified independently before the next begins.

---

## Step 1 — Markdown Parser Service

**File:** `src/knowledge_garden/services/parser.py`

**Description:** Implement `MarkdownParser`, a class with a single `parse_vault` method that walks a directory and returns `Note` objects.

**Done when:**
- `parse_vault(vault_config)` recursively finds all `.md` files in the vault path.
- Each `.md` file produces exactly one `Note` with `title`, `content`, `vault`, `original_path`, `outgoing_links`, and `attachment_refs` set correctly.
- Non-`.md` files are silently skipped.
- Wikilinks are classified into three categories: note links (into `outgoing_links`), inline note transclusions (also into `outgoing_links`), and attachment references (into `attachment_refs`).
- Note links: `[[target]]`, `[[target#heading]]`, `[[target|alias]]`, `[[target#heading|alias]]` — heading fragments and aliases stripped, only the note name retained.
- Inline transclusions: `![[target]]`, `![[target#heading]]`, `![[target|alias]]` where the target has no extension or a `.md` extension — treated as note references in `outgoing_links`.
- Attachment references: `![[file.png]]`, `[[file.pdf]]`, etc. — any wikilink where the target (after stripping fragment and alias) has a non-`.md` file extension goes into `attachment_refs`.
- Notes with no wikilinks have `outgoing_links = []` and `attachment_refs = []`.
- An empty vault directory returns an empty list.
- All unit tests for the parser pass.

---

## Step 2 — Chunker Service

**File:** `src/knowledge_garden/services/chunker.py`

**Description:** Implement `NoteChunker`, a class with a single `chunk_note` method that splits a `Note` into a list of `Chunk` objects.

**Done when:**
- Content is split at ALL markdown heading levels (`#`, `##`, `###`, `####`, `#####`, `######`).
- Each chunk carries `heading_context` set to the heading text that introduced the section, stripped of all leading `#` characters and surrounding whitespace (e.g., `## My Section` → `"My Section"`). Sections before any heading have `heading_context = ""`.
- The heading line itself is NOT included in the chunk's body content.
- If a section's body text exceeds `ChunkingConfig.max_chunk_size` characters, it is further split by double-newline paragraph boundaries.
- Chunks smaller than `ChunkingConfig.min_chunk_size` characters (after stripping whitespace) are discarded.
- `index` values are assigned sequentially starting from 0 across the note.
- `note_id` is set to the parent `Note.id`.
- `embedding` is always `None` (embedding is not the chunker's responsibility).
- A note with no headings produces one chunk containing the whole content (if it meets min size).
- All unit tests for the chunker pass.

---

## Step 3 — HuggingFace Embedder

**Files:** `src/knowledge_garden/config.py`, `src/knowledge_garden/services/hf_embedder.py`, `src/knowledge_garden/main.py`

**Description:** Add `HuggingFaceConfig` to config, implement `HuggingFaceEmbedder` (a second `EmbeddingService` implementation using the HuggingFace Inference API), and update the lifespan provider dispatch so the embedder is selected by `config.embedding.provider`.

**Done when:**
- `HuggingFaceConfig(api_key, base_url)` is a valid Pydantic model in `config.py`.
- `Config.hugging_face: HuggingFaceConfig | None = None` is present on the `Config` model.
- `Config.from_yaml()` reads `HF_API_TOKEN` from env and injects it into `hugging_face.api_key`; if no `hugging_face` section exists in YAML but the token is set, the section is created automatically.
- `HuggingFaceEmbedder` implements the `EmbeddingService` ABC and passes all unit tests in `tests/test_hf_embedder.py`.
- The lifespan in `main.py` dispatches on `config.embedding.provider`: `"together"` → `TogetherAIEmbedder`, `"huggingface"` → `HuggingFaceEmbedder`, unknown value → `ValueError`.
- `"together"` provider path continues to work exactly as before.
- All unit tests for config, the embedder, and the lifespan dispatch pass.

---

## Step 4 — API Router Module

**File:** `src/knowledge_garden/api/routes.py`

**Description:** Create the FastAPI router that will hold the ingestion and notes endpoints. Register it on the `app` in `main.py`.

**Done when:**
- `src/knowledge_garden/api/__init__.py` exists.
- `src/knowledge_garden/api/routes.py` exports an `APIRouter` instance named `router`.
- `main.py` imports `router` and registers it with `app.include_router(router)`.
- Existing `GET /api/v1/health` continues to pass its tests.

---

## Step 5 — Ingest Endpoint

**Endpoint:** `POST /api/v1/ingest`

**Description:** Implement the full ingestion pipeline endpoint.

**Done when:**
- `POST /api/v1/ingest` with `{"vault_name": "unknown"}` returns HTTP 404 with `{"detail": "Vault 'unknown' not found in configuration"}`.
- `POST /api/v1/ingest` with a valid vault name runs the full pipeline and returns `{"vault": ..., "notes_parsed": ..., "chunks_created": ..., "duration_seconds": ...}`.
- Notes and chunks are upserted to Neo4j via `app.state.graph_store`.
- Chunks are embedded via `app.state.embedder` before upserting.
- An empty vault (no `.md` files) returns `notes_parsed: 0, chunks_created: 0`.
- All unit tests for the endpoint pass (with mocked dependencies).

---

## Step 6 — Notes Listing Endpoint

**Endpoint:** `GET /api/v1/notes`

**Description:** Implement the notes listing endpoint.

**Done when:**
- `GET /api/v1/notes` with an empty graph returns `{"notes": [], "total": 0}`.
- `GET /api/v1/notes` with notes in the graph returns the correct list and total count.
- Each note in the response includes `id`, `title`, `vault`, `original_path`, and `outgoing_links`.
- All unit tests for the endpoint pass.
