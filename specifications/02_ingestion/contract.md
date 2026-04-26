# Contract: Vault Ingestion

Builds on: `specifications/01_foundation/contract.md`

Uses `Note`, `Chunk` from `src/knowledge_garden/models/note.py` (spec 01).
Uses `GraphStore` ABC from `src/knowledge_garden/services/graph_store.py` (spec 01).
Uses `EmbeddingService` ABC from `src/knowledge_garden/services/embedder.py` (spec 01).
Uses `VaultConfig`, `ChunkingConfig` from `src/knowledge_garden/config.py` (spec 01).

---

## 0. Model Amendment — Note.attachment_refs

### 0.1 Change

File: `src/knowledge_garden/models/note.py`

Add the following field to the `Note` model (after `outgoing_links`):

```python
attachment_refs: list[str] = []  # non-note attachment targets from wikilinks (images, PDFs, etc.)
```

This is an additive change with a default value. No existing Phase 01 tests are broken.

**Rationale:** During parsing, wikilinks that target files with non-`.md` extensions (e.g., `![[image.png]]`, `[[report.pdf]]`) are not note references. Storing them separately in `attachment_refs` preserves the information for the future exporter phase without polluting `outgoing_links`.

### 0.2 Model Amendment Test

File: `tests/test_models.py`

| Test function | Marker | Setup | Expected outcome |
|---|---|---|---|
| `test_note_attachment_refs_default_empty` | `@pytest.mark.unit` | Create `Note` without passing `attachment_refs` | `note.attachment_refs == []` |

---

## 1. Markdown Parser Service

### 1.1 Interface

File: `src/knowledge_garden/services/parser.py`

```python
import re
from pathlib import Path
from knowledge_garden.config import VaultConfig
from knowledge_garden.models.note import Note

# Matches both transclusion (![[...]]) and standard ([[...]]) wikilinks.
# Group 1: "!" if transclusion prefix present, else empty string.
# Group 2: the raw inner content (everything between [[ and ]]).
WIKILINK_RE = re.compile(r"(!?)\[\[([^\]]+)\]\]")

# File extensions that identify attachment targets (non-note files).
ATTACHMENT_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".pdf", ".mp4", ".mov", ".webm",
    ".zip", ".csv", ".xlsx",
}

class MarkdownParser:
    """Parses a vault directory into Note objects.

    Walks the vault path recursively, reads every .md file,
    extracts wikilinks, and returns Note objects. Does not embed
    or write to any storage backend.
    """

    def parse_vault(self, vault_config: VaultConfig) -> list[Note]:
        """Walk vault_config.path recursively and parse all .md files.

        Parameters
        ----------
        vault_config:
            VaultConfig with .name (vault identifier) and .path
            (absolute path to the vault root directory).

        Returns
        -------
        list[Note]
            One Note per .md file found. Files that are not .md are
            silently skipped. Returns [] if the directory is empty or
            contains no .md files.
        """
        ...

    def parse_file(self, file_path: Path, vault_root: Path, vault_name: str) -> Note:
        """Parse a single .md file into a Note.

        Parameters
        ----------
        file_path:
            Absolute path to the .md file.
        vault_root:
            Absolute path to the vault root (used to compute original_path).
        vault_name:
            The vault identifier string (from VaultConfig.name).

        Returns
        -------
        Note
            title           = file_path.stem (filename without extension)
            content         = raw text of the file
            vault           = vault_name
            original_path   = str(file_path.relative_to(vault_root))
            outgoing_links  = note wikilink targets (fragments and aliases stripped)
            attachment_refs = attachment wikilink targets (non-.md extensions)
        """
        ...

    def extract_wikilinks(self, content: str) -> tuple[list[str], list[str]]:
        """Classify all [[...]] and ![[...]] patterns in markdown content.

        Classification rules (applied after stripping #fragment and |alias
        from the raw target):

        - If the resolved target has no file extension, or has a .md
          extension → note link → goes into note_links.
        - If the resolved target has any other file extension → attachment
          reference → goes into attachment_refs.
        - ![[target]] where target resolves to a note → inline transclusion;
          treated as a note link (goes into note_links).
        - ![[file.png]] → attachment reference.

        Fragment stripping: "note#heading" → "note"
        Alias stripping:    "note|alias"   → "note"
        Both combined:      "note#heading|alias" → "note"

        Duplicates are preserved (raw extraction, no dedup).

        Parameters
        ----------
        content:
            Raw markdown text.

        Returns
        -------
        tuple[list[str], list[str]]
            (note_links, attachment_refs)
            note_links      — ordered list of resolved note target strings
            attachment_refs — ordered list of attachment filename strings
        """
        ...
```

### 1.2 Parser Test Specifications

File: `tests/test_parser.py`

All tests are `@pytest.mark.unit`.

Fixtures needed:
- `tmp_path` (built-in pytest fixture)
- `sample_vault_config(tmp_path)` — a `VaultConfig` pointing at `tmp_path`, name `"test_vault"`

#### Test cases

| Test function | Setup | Expected outcome |
|---|---|---|
| `test_parse_vault_empty_directory` | `tmp_path` is empty | Returns `[]` |
| `test_parse_vault_skips_non_md_files` | `tmp_path` contains `note.txt`, `image.png` | Returns `[]` |
| `test_parse_vault_single_note` | One file `hello.md` with content `"# Hello\nWorld"` | Returns list of length 1; `note.title == "hello"`, `note.vault == "test_vault"`, `note.content == "# Hello\nWorld"` |
| `test_parse_vault_original_path` | File at `subdir/nested.md` inside vault root | `note.original_path == "subdir/nested.md"` |
| `test_parse_vault_nested_directories` | Files at `a/b.md`, `c.md`, `d/e/f.md` | Returns 3 notes |
| `test_parse_vault_mixed_files` | Files `note.md`, `image.png`, `data.csv`, `other.md` | Returns 2 notes |
| `test_parse_vault_no_links` | File with no `[[...]]` syntax | `note.outgoing_links == []` and `note.attachment_refs == []` |
| `test_parse_vault_note_has_uuid` | Parse any vault with one file | `note.id` is a valid UUID, not `None` |
| `test_extract_wikilinks_simple` | Content `"See [[Other Note]]"` | `note_links == ["Other Note"]`, `attachment_refs == []` |
| `test_extract_wikilinks_with_alias` | Content `"See [[target\|Display Text]]"` | `note_links == ["target"]`, `attachment_refs == []` |
| `test_extract_wikilinks_multiple` | Content `"[[A]] and [[B\|alias]] and [[C]]"` | `note_links == ["A", "B", "C"]`, `attachment_refs == []` |
| `test_extract_wikilinks_no_links` | Content `"No links here"` | `([], [])` |
| `test_extract_wikilinks_empty_string` | Content `""` | `([], [])` |
| `test_extract_wikilinks_preserves_duplicates` | Content `"[[A]] and [[A]]"` | `note_links == ["A", "A"]` |
| `test_extract_wikilinks_heading_fragment` | Content `"[[note#heading]]"` | `note_links == ["note"]`, `attachment_refs == []` |
| `test_extract_wikilinks_heading_and_alias` | Content `"[[note#heading\|alias]]"` | `note_links == ["note"]`, `attachment_refs == []` |
| `test_extract_wikilinks_transclusion_note` | Content `"![[note]]"` | `note_links == ["note"]`, `attachment_refs == []` (inline transclusion of a note) |
| `test_extract_wikilinks_transclusion_heading` | Content `"![[note#section]]"` | `note_links == ["note"]`, `attachment_refs == []` |
| `test_extract_wikilinks_transclusion_image` | Content `"![[image.png]]"` | `note_links == []`, `attachment_refs == ["image.png"]` |
| `test_extract_wikilinks_transclusion_pdf` | Content `"![[document.pdf]]"` | `note_links == []`, `attachment_refs == ["document.pdf"]` |
| `test_extract_wikilinks_standard_attachment` | Content `"[[report.pdf]]"` | `note_links == []`, `attachment_refs == ["report.pdf"]` |
| `test_extract_wikilinks_mixed` | Content `"[[Note A]] ![[image.png]] [[Note B\|alias]] ![[note C]] [[doc.pdf]]"` | `note_links == ["Note A", "Note B", "note C"]`, `attachment_refs == ["image.png", "doc.pdf"]` (document order preserved within each list) |
| `test_parse_file_sets_title_from_stem` | File `My Note.md` | `note.title == "My Note"` |
| `test_parse_file_sets_outgoing_links` | File content has `"[[Link A]]"` and `"[[Link B\|alias]]"` | `note.outgoing_links == ["Link A", "Link B"]` |
| `test_parse_file_sets_attachment_refs` | File content has `"![[image.png]]"` and `"[[report.pdf]]"` | `note.attachment_refs == ["image.png", "report.pdf"]` |

---

## 2. Chunker Service

### 2.1 Interface

File: `src/knowledge_garden/services/chunker.py`

```python
from knowledge_garden.config import ChunkingConfig
from knowledge_garden.models.note import Chunk, Note

class NoteChunker:
    """Splits a Note into Chunk objects based on heading structure and size limits.

    Splitting rules:
    1. Content is split at ALL markdown heading levels: #, ##, ###, ####,
       #####, ######. Every heading line is a split point.
    2. The heading line itself is NOT included in the chunk body content.
       heading_context stores the heading text with all leading # characters
       and surrounding whitespace stripped (e.g., "## My Section" → "My Section").
       Content before the first heading of any level has heading_context = "".
    3. If a section's body text length exceeds max_chunk_size, it is further
       split by double-newline paragraph boundaries (splitting on "\n\n").
       Each paragraph sub-chunk inherits the same heading_context.
    4. Chunks with fewer than min_chunk_size characters (after stripping
       whitespace) are discarded.
    5. Surviving chunks are assigned sequential index values starting at 0.
    6. note_id is set to the parent Note.id on every chunk.
    7. embedding is always None.
    """

    def __init__(self, config: ChunkingConfig) -> None:
        """
        Parameters
        ----------
        config:
            ChunkingConfig providing max_chunk_size and min_chunk_size.
        """
        ...

    def chunk_note(self, note: Note) -> list[Chunk]:
        """Split a Note into an ordered list of Chunk objects.

        Parameters
        ----------
        note:
            The Note to chunk. Uses note.content and note.id.

        Returns
        -------
        list[Chunk]
            Ordered list of chunks (by index). May be empty if all sections
            are smaller than min_chunk_size.
        """
        ...
```

### 2.2 Chunker Test Specifications

File: `tests/test_chunker.py`

All tests are `@pytest.mark.unit`.

Fixtures needed:
- `default_chunking_config` — `ChunkingConfig(max_chunk_size=1000, min_chunk_size=10)`
- `small_chunking_config` — `ChunkingConfig(max_chunk_size=50, min_chunk_size=10)`
- `sample_note(content)` — helper that returns a `Note` with given content, `title="test"`, `vault="v"`, `original_path="test.md"`

#### Test cases

| Test function | Setup | Expected outcome |
|---|---|---|
| `test_chunk_note_no_headings` | Content = `"Just some plain text here with enough words."`, `min_chunk_size=10` | Returns 1 chunk; `chunks[0].content` contains the text; `chunks[0].heading_context == ""`; `chunks[0].index == 0` |
| `test_chunk_note_no_headings_below_min` | Content = `"Hi"`, `min_chunk_size=10` | Returns `[]` |
| `test_chunk_note_single_h2` | Content = `"## Section\nSome content here."` | Returns 1 chunk; `chunks[0].heading_context == "Section"`; heading line not in `chunks[0].content` |
| `test_chunk_note_h1_splits_content` | Content = `"# Title\nIntro text.\n## Section\nSection content."` with both sections meeting min_chunk_size | Returns 2 chunks: `chunks[0].heading_context == "Title"`, `chunks[1].heading_context == "Section"` |
| `test_chunk_note_multiple_h2` | Content has 3 `##` sections each with sufficient content | Returns 3 chunks with sequential indices 0, 1, 2 |
| `test_chunk_note_sequential_indices` | Content with 4 sections | `[c.index for c in chunks] == [0, 1, 2, 3]` |
| `test_chunk_note_sets_note_id` | Any note | All chunks have `chunk.note_id == note.id` |
| `test_chunk_note_embedding_is_none` | Any note | All chunks have `chunk.embedding is None` |
| `test_chunk_note_oversized_section_split_by_paragraph` | Section text is 200 chars, `max_chunk_size=50`; paragraphs separated by `"\n\n"` | Returns multiple chunks, each under `max_chunk_size` |
| `test_chunk_note_paragraph_split_inherits_heading_context` | Oversized section under `## Section` split into 2 paragraph chunks | Both chunks have `heading_context == "Section"` |
| `test_chunk_note_below_min_discarded` | Section with 5 chars, `min_chunk_size=10` | That section produces no chunk |
| `test_chunk_note_empty_content` | Content = `""` | Returns `[]` |
| `test_chunk_note_h3_is_split_point` | Content has `### SubSection\nEnough content here.` | Produces a chunk with `heading_context == "SubSection"` |
| `test_chunk_note_heading_context_no_hashes` | Heading line `"## My Heading"` | `chunks[0].heading_context == "My Heading"` (no `#` characters, no extra whitespace) |
| `test_chunk_note_heading_not_in_body` | Content = `"## Section\nBody text."` | `"## Section"` does not appear in `chunks[0].content`; `chunks[0].content` contains `"Body text."` |

**Note on H1 behavior:** `#` headings are split points just like all other heading levels. Content after a `#` heading up to the next heading is a chunk with `heading_context` set to the H1 heading text (stripped of `#` and whitespace). Content that appears before any heading at all has `heading_context = ""`.

---

## 3. HuggingFace Embedder

### 3.1 Config Additions

File: `src/knowledge_garden/config.py`

Add a new top-level Pydantic model:

```python
class HuggingFaceConfig(BaseModel):
    api_key: str        # injected from env: HF_API_TOKEN
    base_url: str = "https://api-inference.huggingface.co"
```

Add to `Config`:

```python
hugging_face: HuggingFaceConfig | None = None
```

Update `Config.from_yaml()`: after the existing `TOGETHER_API_KEY` and `NEO4J_URI` overrides, add:

```python
hf_api_token = os.environ.get("HF_API_TOKEN")
if hf_api_token is not None:
    hf_section: dict = data.get("hugging_face") or {}
    hf_section["api_key"] = hf_api_token
    data["hugging_face"] = hf_section
```

If `HF_API_TOKEN` is set but there is no `hugging_face` section in the YAML, the code above creates the section with just `api_key`. If the section already exists (e.g., to override `base_url`), the token is merged in and the existing keys are preserved.

### 3.2 HuggingFace Embedder Interface

File: `src/knowledge_garden/services/hf_embedder.py`

```python
import httpx
from knowledge_garden.config import EmbeddingConfig, HuggingFaceConfig
from knowledge_garden.services.embedder import EmbeddingService


class HuggingFaceEmbedder(EmbeddingService):
    """Embedding via the HuggingFace Inference API (feature-extraction endpoint).

    Uses the hosted inference API at api-inference.huggingface.co.
    Endpoint: POST /models/{model_id}
    Request body: {"inputs": ["text1", "text2"]}
    Response: [[float, ...], [float, ...]]  — a bare JSON array of vectors,
              one inner list per input text. No wrapper object.

    This differs from the Together AI response format, which wraps vectors
    in {"data": [{"embedding": [...]}, ...]}.
    """

    def __init__(self, hf_config: HuggingFaceConfig, embedding_config: EmbeddingConfig) -> None:
        """
        Parameters
        ----------
        hf_config:
            HuggingFaceConfig with api_key and base_url.
        embedding_config:
            EmbeddingConfig with model, dimension, and batch_size.
        """
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts via HuggingFace feature-extraction endpoint.

        Returns [] immediately for empty input without making an HTTP call.
        Batches input by batch_size; each batch is a separate POST request.

        Parameters
        ----------
        texts:
            List of strings to embed.

        Returns
        -------
        list[list[float]]
            One embedding vector per input text, in input order.

        Raises
        ------
        httpx.HTTPStatusError
            If any batch request returns a non-2xx status (e.g., 503 while
            the model is loading on the HuggingFace side).
        """
        ...

    def dimension(self) -> int:
        """Return the configured embedding dimension."""
        ...

    async def close(self) -> None:
        """Close the underlying httpx.AsyncClient."""
        ...
```

**HTTP details:**
- URL template: `POST /models/{self._model}` (relative to `hf_config.base_url`)
- Request JSON: `{"inputs": batch}` where `batch` is a `list[str]`
- Response JSON: `list[list[float]]` — parse directly, no key traversal
- Always call `response.raise_for_status()` before reading the body

### 3.3 Lifespan Provider Dispatch

File: `src/knowledge_garden/main.py`

Replace the hard-coded `TogetherAIEmbedder(...)` call with a conditional block:

```python
if config.embedding.provider == "together":
    embedder = TogetherAIEmbedder(config.together_ai, config.embedding)
elif config.embedding.provider == "huggingface":
    if config.hugging_face is None:
        raise ValueError(
            "hugging_face config section required when provider is 'huggingface'"
        )
    embedder = HuggingFaceEmbedder(config.hugging_face, config.embedding)
else:
    raise ValueError(f"Unknown embedding provider: {config.embedding.provider}")
```

Add the import:

```python
from knowledge_garden.services.hf_embedder import HuggingFaceEmbedder
```

The rest of the lifespan (graph store init, state assignment, shutdown) is unchanged.

### 3.4 Config Test Specifications

File: `tests/test_config.py`

All tests are `@pytest.mark.unit`.

| Test function | Setup | Expected outcome |
|---|---|---|
| `test_config_hf_section_optional` | YAML has no `hugging_face` key; `HF_API_TOKEN` not set | `config.hugging_face is None` |
| `test_config_hf_env_token_override` | `HF_API_TOKEN="tok123"` set in env; YAML has no `hugging_face` section | `config.hugging_face.api_key == "tok123"`; `config.hugging_face.base_url == "https://api-inference.huggingface.co"` (default) |
| `test_config_hf_env_token_merges` | `HF_API_TOKEN="tok456"` set in env; YAML `hugging_face.base_url = "https://custom.hf.co"` | `config.hugging_face.api_key == "tok456"`; `config.hugging_face.base_url == "https://custom.hf.co"` (preserved) |

Fixtures needed: `tmp_path` (built-in), a helper that writes a minimal valid YAML to `tmp_path / "config.yaml"` and calls `Config.from_yaml()`.

### 3.5 HuggingFace Embedder Unit Test Specifications

File: `tests/test_hf_embedder.py`

All tests are `@pytest.mark.unit`.

**HF response format note:** The mock HTTP response for HF tests must return a bare `list[list[float]]` (e.g., `[[0.1, 0.2, ...], [0.3, 0.4, ...]]`), not the `{"data": [...]}` object used in Together AI tests. The `embed` implementation must parse this bare array directly.

Fixtures needed:
- `hf_config` — `HuggingFaceConfig(api_key="test-token")`
- `embedding_config` — `EmbeddingConfig(model="sentence-transformers/all-MiniLM-L6-v2", dimension=384, batch_size=64)`

| Test function | Marker | Setup | Expected outcome |
|---|---|---|---|
| `test_hf_embed_single_text` | unit | Mock httpx returns `[[0.1] * 384]` | `embed(["hello"])` returns a list of length 1; `result[0]` has 384 floats |
| `test_hf_embed_batch` | unit | Mock httpx returns `[[0.1] * 384, [0.2] * 384, [0.3] * 384]` | `embed(["a", "b", "c"])` returns a list of length 3 |
| `test_hf_embed_batching_splits_large_input` | unit | `batch_size=64`; mock httpx returns 64 vectors per call | `embed(["x"] * 100)` makes exactly 2 HTTP POST calls |
| `test_hf_embed_empty_list` | unit | No mock needed | `embed([])` returns `[]`; no HTTP call is made |
| `test_hf_embed_api_error_propagates` | unit | Mock httpx returns HTTP 503 | `embed(["text"])` raises `httpx.HTTPStatusError` |
| `test_hf_dimension_returns_configured` | unit | `EmbeddingConfig(dimension=384)` | `embedder.dimension() == 384` |
| `test_hf_close_closes_client` | unit | Normal construction | After `await embedder.close()`, `embedder._client.is_closed is True` |

**Mocking strategy:** Use `unittest.mock.AsyncMock` or `respx` to intercept `httpx.AsyncClient.post`. The mock for the HF API must return a response whose `.json()` yields a bare `list[list[float]]`.

### 3.6 Lifespan Provider Dispatch Test Specifications

File: `tests/test_api.py`

All tests are `@pytest.mark.unit`.

These tests exercise only the provider-dispatch logic, not the full lifespan (which requires real Neo4j). Patch `Config.from_yaml` and service constructors as needed.

| Test function | Marker | Setup | Expected outcome |
|---|---|---|---|
| `test_lifespan_selects_together_embedder` | unit | `config.embedding.provider = "together"`; `config.together_ai` present | `TogetherAIEmbedder` is instantiated; no `ValueError` raised |
| `test_lifespan_selects_hf_embedder` | unit | `config.embedding.provider = "huggingface"`; `config.hugging_face` present | `HuggingFaceEmbedder` is instantiated; no `ValueError` raised |
| `test_lifespan_unknown_provider_raises` | unit | `config.embedding.provider = "unknown"` | `ValueError` raised with message containing `"Unknown embedding provider"` |

---

## 4. API Request/Response Schemas

File: `src/knowledge_garden/api/routes.py`

All schemas are Pydantic v2 `BaseModel` classes defined in the same file or a sibling `src/knowledge_garden/api/schemas.py`.

### 4.1 Ingest Endpoint Schemas

```python
class IngestRequest(BaseModel):
    vault_name: str  # must match a name in config.vaults

class IngestResponse(BaseModel):
    vault: str            # the vault_name from the request
    notes_parsed: int     # number of Note objects produced by parser
    chunks_created: int   # total number of Chunk objects after chunking
    duration_seconds: float  # wall-clock seconds for the full pipeline
```

### 4.2 Note Summary Schema (for listing endpoint)

```python
class NoteSummary(BaseModel):
    id: str              # UUID as string
    title: str
    vault: str
    original_path: str
    outgoing_links: list[str]

class NotesListResponse(BaseModel):
    notes: list[NoteSummary]
    total: int           # len(notes)
```

---

## 5. API Endpoints

### 5.1 POST /api/v1/ingest

**Handler function:** `ingest_vault` in `src/knowledge_garden/api/routes.py`

**Method/Path:** `POST /api/v1/ingest`

**Request body:** `IngestRequest`

**Response (200):** `IngestResponse`

**Error cases:**

| Condition | Status | Body |
|---|---|---|
| `vault_name` not in `app.state.config.vaults` | 404 | `{"detail": "Vault '{vault_name}' not found in configuration"}` |

**Pipeline (in order):**
1. Look up `VaultConfig` by matching `vault_name` to each `vault.name` in `app.state.config.vaults`. Raise `HTTPException(404)` if not found.
2. Record start time with `time.monotonic()`.
3. Call `MarkdownParser().parse_vault(vault_config)` → `notes: list[Note]`.
4. For each note, call `NoteChunker(app.state.config.chunking).chunk_note(note)`. Accumulate all chunks into a flat list.
5. Extract `chunk.content` for all chunks, call `await app.state.embedder.embed(texts)` → embedding vectors. Assign each vector back to its chunk (`chunk.embedding = vector`).
6. For each note, call `await app.state.graph_store.upsert_note(note)`.
7. For each chunk, call `await app.state.graph_store.upsert_chunk(chunk)`.
8. Record end time and compute `duration_seconds = time.monotonic() - start`.
9. Return `IngestResponse(vault=vault_name, notes_parsed=len(notes), chunks_created=len(all_chunks), duration_seconds=duration_seconds)`.

**Embedding batch note:** Pass all chunk texts to `embed()` in a single call. The embedder handles internal batching per `EmbeddingConfig.batch_size`. Do not loop per chunk.

**Empty vault behavior:** If `parse_vault` returns `[]`, the embed call is skipped (no texts to embed), upsert loops do not execute, and the response has `notes_parsed=0, chunks_created=0`.

### 5.2 GET /api/v1/notes

**Handler function:** `list_notes` in `src/knowledge_garden/api/routes.py`

**Method/Path:** `GET /api/v1/notes`

**Request body:** None

**Response (200):** `NotesListResponse`

**Pipeline:**
1. Call `await app.state.graph_store.get_all_notes()` → `notes: list[Note]`.
2. Convert each `Note` to `NoteSummary(id=str(note.id), title=note.title, vault=note.vault, original_path=note.original_path, outgoing_links=note.outgoing_links)`.
3. Return `NotesListResponse(notes=summaries, total=len(summaries))`.

---

## 6. Router Registration

File modifications to `src/knowledge_garden/main.py`:

```python
from knowledge_garden.api.routes import router

app.include_router(router)
```

The router is defined with `prefix="/api/v1"` and no tags beyond what FastAPI infers.

New files:
- `src/knowledge_garden/api/__init__.py` (empty)
- `src/knowledge_garden/api/routes.py` (contains `router`, `IngestRequest`, `IngestResponse`, `NoteSummary`, `NotesListResponse`, `ingest_vault`, `list_notes`)

---

## 7. Test Specifications

### 7.1 Ingest Endpoint Tests

File: `tests/test_ingest_api.py`

All tests are `@pytest.mark.unit` and use `httpx.AsyncClient` with the FastAPI app (via `ASGITransport`), or `pytest`'s `TestClient`. Dependencies are injected by overriding `app.state` in a fixture.

**Fixtures needed:**

```python
# In tests/test_ingest_api.py or conftest.py

@pytest.fixture
def mock_parser():
    """Returns a MarkdownParser whose parse_vault returns a controlled list."""
    ...

@pytest.fixture
def mock_chunker():
    """Returns a NoteChunker whose chunk_note returns a controlled list."""
    ...

@pytest.fixture
def app_with_mocks(mock_embedder, mock_graph_store):
    """
    FastAPI app with app.state pre-populated:
      app.state.embedder     = mock_embedder (from spec 01 conftest)
      app.state.graph_store  = mock_graph_store (from spec 01 conftest)
      app.state.config       = a Config with one VaultConfig(name="test_vault", path="/tmp/test")
    The lifespan is NOT used — state is set directly.
    """
    ...
```

**Pattern for overriding app.state in tests:**

Use `app.state` assignment before creating the test client. Because the lifespan connects to real services, tests must bypass it. Use one of:
- `anyio` + `httpx.AsyncClient(app=app, base_url="http://test")` with a custom lifespan override, or
- `TestClient` with `raise_server_exceptions=True` and a patched lifespan.

The recommended approach: create a separate `FastAPI` app instance in the fixture (not the production `app`) without a lifespan, set `state` manually, and include the router.

```python
from fastapi import FastAPI
from knowledge_garden.api.routes import router as api_router

@pytest.fixture
def test_app(mock_embedder, mock_graph_store, tmp_path):
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    # build a minimal Config
    from knowledge_garden.config import (
        Config, VaultConfig, TogetherAIConfig, ChunkingConfig,
        Neo4jConfig, EmbeddingConfig, LLMConfig, LinkingConfig, ExportConfig
    )
    app.state.config = Config(
        vaults=[VaultConfig(name="test_vault", path=str(tmp_path))],
        together_ai=TogetherAIConfig(api_key="fake"),
    )
    app.state.embedder = mock_embedder
    app.state.graph_store = mock_graph_store
    return app
```

#### Test cases

| Test function | Setup | Input | Expected outcome |
|---|---|---|---|
| `test_ingest_vault_not_found` | `test_app` with `vaults=[VaultConfig(name="test_vault", ...)]` | `POST /api/v1/ingest {"vault_name": "unknown"}` | 404, body contains `"Vault 'unknown' not found in configuration"` |
| `test_ingest_happy_path` | `tmp_path` has 2 `.md` files; mocks return controlled notes/chunks/embeddings | `POST /api/v1/ingest {"vault_name": "test_vault"}` | 200; `notes_parsed == 2`; `chunks_created == correct count`; `duration_seconds >= 0` |
| `test_ingest_empty_vault` | `tmp_path` is empty | `POST /api/v1/ingest {"vault_name": "test_vault"}` | 200; `notes_parsed == 0`; `chunks_created == 0` |
| `test_ingest_calls_upsert_note` | 1 `.md` file in `tmp_path` | `POST /api/v1/ingest {"vault_name": "test_vault"}` | `mock_graph_store.upsert_note` called at least once |
| `test_ingest_calls_upsert_chunk` | 1 `.md` file with content that produces chunks | `POST /api/v1/ingest {"vault_name": "test_vault"}` | `mock_graph_store.upsert_chunk` called at least once |
| `test_ingest_calls_embedder` | 1 `.md` file with content that produces chunks | `POST /api/v1/ingest {"vault_name": "test_vault"}` | `mock_embedder.embed` called once |
| `test_ingest_embed_not_called_for_empty_vault` | `tmp_path` is empty | `POST /api/v1/ingest {"vault_name": "test_vault"}` | `mock_embedder.embed` NOT called |
| `test_ingest_response_schema` | 1 `.md` file | valid request | Response JSON has keys `vault`, `notes_parsed`, `chunks_created`, `duration_seconds` |

### 7.2 Notes Listing Endpoint Tests

File: `tests/test_notes_api.py`

All tests are `@pytest.mark.unit`. Uses the same `test_app` fixture pattern.

#### Test cases

| Test function | Setup | Expected outcome |
|---|---|---|
| `test_list_notes_empty` | `mock_graph_store.get_all_notes` returns `[]` | 200; `{"notes": [], "total": 0}` |
| `test_list_notes_returns_correct_count` | `mock_graph_store.get_all_notes` returns 3 `Note` objects | `total == 3`; `len(notes) == 3` |
| `test_list_notes_schema` | `mock_graph_store.get_all_notes` returns 1 `Note` | Each note in response has `id`, `title`, `vault`, `original_path`, `outgoing_links` |
| `test_list_notes_id_is_string` | `mock_graph_store.get_all_notes` returns 1 `Note` | `notes[0]["id"]` is a string (UUID serialized) |
| `test_list_notes_outgoing_links` | Note has `outgoing_links=["A", "B"]` | `notes[0]["outgoing_links"] == ["A", "B"]` |

### 7.3 Parser Tests (already listed in section 1.2 above)

File: `tests/test_parser.py` — see section 1.2.

### 7.4 Chunker Tests (already listed in section 2.2 above)

File: `tests/test_chunker.py` — see section 2.2.

---

## 8. Fixture Files

### 8.1 Sample Vault Fixture

Directory: `tests/fixtures/sample_vault/`

Structure:
```
tests/fixtures/sample_vault/
  note_a.md       — has wikilinks: [[Note B]], [[Note C|Alias]]
  note_b.md       — no wikilinks, multiple headings
  subdir/
    note_c.md     — one heading, short content
```

`note_a.md` content:
```markdown
# Note A

Introduction paragraph.

## Section 1

See also [[Note B]] and [[Note C|Alias]].

![[diagram.png]]

## Section 2

More content here. See [[report.pdf]].
```

`note_b.md` content:
```markdown
# Note B

This is content directly under the H1 heading.

## Overview

This is the overview section with enough content to pass min_chunk_size checks.

## Details

These are the details.
```

`subdir/note_c.md` content:
```markdown
# Note C

## Only Section

Short note.
```

### 8.2 Updated conftest.py additions

The following fixtures should be added to `tests/conftest.py` (additions only — do not remove existing fixtures from spec 01):

```python
import pytest
from knowledge_garden.config import VaultConfig, ChunkingConfig

@pytest.fixture
def sample_vault_config(tmp_path) -> VaultConfig:
    """VaultConfig pointing at tmp_path, named 'test_vault'."""
    return VaultConfig(name="test_vault", path=str(tmp_path))

@pytest.fixture
def default_chunking_config() -> ChunkingConfig:
    return ChunkingConfig(max_chunk_size=1000, min_chunk_size=10)

@pytest.fixture
def small_chunking_config() -> ChunkingConfig:
    return ChunkingConfig(max_chunk_size=50, min_chunk_size=10)
```

---

## 9. Dependencies and Assumptions

- `MarkdownParser` uses only the Python standard library (`pathlib`, `re`). No new dependencies.
- `NoteChunker` uses only the Python standard library. No new dependencies.
- `HuggingFaceEmbedder` uses `httpx` (already a project dependency from spec 01). No new package dependencies are introduced.
- The ingest endpoint uses `time` (standard library) for timing.
- The router uses `fastapi.APIRouter` and `fastapi.HTTPException`.
- All endpoint handlers access services via `request.app.state` (FastAPI `Request` object), not via Depends injection.
- `mock_embedder.embed` must be configured to return a list of vectors matching the number of chunks. In tests that produce N chunks, set `mock_embedder.embed.return_value = [[0.1] * 768] * N`.
- The `resolved_links` field on `Note` is not populated during ingestion; it remains `[]`. Link resolution is a future phase.
- When `config.embedding.provider` is `"huggingface"`, `config.hugging_face` must not be `None`. The lifespan raises `ValueError` immediately at startup if this invariant is violated.
