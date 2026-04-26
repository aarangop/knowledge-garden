# Contract: Config Split

**STATUS: FROZEN**

Amends: none. This is an independent amendment to the configuration layer originally defined in `specifications/01_foundation/contract.md` section 1. The old `Config` class and `from_yaml()` specified there are superseded entirely by this spec.

---

## 1. File Locations

| File | Change |
|------|--------|
| `src/knowledge_garden/config.py` | Rewritten — old `Config`, `Neo4jConfig`, `TogetherAIConfig`, `HuggingFaceConfig` removed; `AppSettings` and `BusinessConfig` added |
| `src/knowledge_garden/main.py` | Updated to use `AppSettings` |
| `src/knowledge_garden/cli.py` | Updated to use `AppSettings` + `BusinessConfig` |
| `tests/test_config.py` | Replaced — all `Config`-based tests removed, new tests for `AppSettings` and `BusinessConfig` added |

---

## 2. `AppSettings`

File: `src/knowledge_garden/config.py`

`AppSettings` extends `pydantic_settings.BaseSettings`. It reads from environment variables and a `.env` file in the working directory. No YAML is involved.

```python
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    # Together AI
    together_api_key: str
    together_base_url: str = "https://api.together.xyz/v1"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "knowledge-garden"
    neo4j_database: str = "neo4j"

    # HuggingFace (optional)
    hf_api_token: str | None = None
    hf_base_url: str = "https://api-inference.huggingface.co"

    # FastAPI server (optional — only used by CLI/compose startup)
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
```

### 2.1 Field Mapping

Environment variable names are the uppercased field names (pydantic-settings default behavior with `case_sensitive=False`):

| Field | Env var | Required | Default |
|-------|---------|----------|---------|
| `together_api_key` | `TOGETHER_API_KEY` | Yes | — |
| `together_base_url` | `TOGETHER_BASE_URL` | No | `"https://api.together.xyz/v1"` |
| `neo4j_uri` | `NEO4J_URI` | No | `"bolt://localhost:7687"` |
| `neo4j_user` | `NEO4J_USER` | No | `"neo4j"` |
| `neo4j_password` | `NEO4J_PASSWORD` | No | `"knowledge-garden"` |
| `neo4j_database` | `NEO4J_DATABASE` | No | `"neo4j"` |
| `hf_api_token` | `HF_API_TOKEN` | No | `None` |
| `hf_base_url` | `HF_BASE_URL` | No | `"https://api-inference.huggingface.co"` |
| `app_host` | `APP_HOST` | No | `"0.0.0.0"` |
| `app_port` | `APP_PORT` | No | `8000` |

### 2.2 Behavior

- `AppSettings()` reads from two sources with this precedence (highest → lowest): (1) actual environment variables, (2) `.env` file on disk.
- In Docker: `docker-compose.yml` injects the `.env` file as real environment variables via `env_file: .env`. The container sees them at priority 1 — no `.env` file needs to be present inside the image.
- In local dev: the `.env` file in the working directory is read at priority 2 by pydantic-settings natively. No explicit `load_dotenv()` call is needed and none is present.
- If `TOGETHER_API_KEY` is absent from both sources, instantiation raises `pydantic_settings.ValidationError`.
- `AppSettings` does NOT accept a YAML path. There is no `from_yaml()` method.

---

## 3. `BusinessConfig`

File: `src/knowledge_garden/config.py`

`BusinessConfig` is a plain `pydantic.BaseModel`. It is loaded exclusively by the CLI from a YAML file. The FastAPI server does not import or instantiate `BusinessConfig`.

```python
from pydantic import BaseModel
from pathlib import Path
import yaml

class VaultConfig(BaseModel):
    name: str
    path: str

class EmbeddingConfig(BaseModel):
    provider: str = "together"
    model: str = "togethercomputer/m2-bert-80M-8k-retrieval"
    dimension: int = 768
    batch_size: int = 64

class LLMConfig(BaseModel):
    provider: str = "together"
    model: str = "THUDM/glm-4-9b-chat"
    max_tokens: int = 1024
    temperature: float = 0.3

class ChunkingConfig(BaseModel):
    max_chunk_size: int = 1000
    min_chunk_size: int = 100

class LinkingConfig(BaseModel):
    threshold: float = 0.7
    max_neighbors: int = 20

class ExportConfig(BaseModel):
    output_dir: str = "./output"

class BusinessConfig(BaseModel):
    vaults: list[VaultConfig] = []
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    linking: LinkingConfig = LinkingConfig()
    export: ExportConfig = ExportConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BusinessConfig":
        """Load BusinessConfig from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A validated BusinessConfig instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            yaml.YAMLError: If the file is not valid YAML.
            pydantic.ValidationError: If the YAML content does not match the schema.
        """
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
```

### 3.1 Removed Sub-models

The following sub-models that previously existed in `config.py` are **removed entirely**:

- `Neo4jConfig` — replaced by flat fields on `AppSettings`
- `TogetherAIConfig` — replaced by flat fields on `AppSettings`
- `HuggingFaceConfig` — replaced by flat fields on `AppSettings`

### 3.2 Preserved Sub-models

These sub-models are preserved unchanged (same field names, same defaults):

- `VaultConfig` — `name: str`, `path: str`
- `EmbeddingConfig` — same fields and defaults as before
- `LLMConfig` — same fields and defaults as before
- `ChunkingConfig` — same fields and defaults as before
- `LinkingConfig` — same fields and defaults as before
- `ExportConfig` — same fields and defaults as before

---

## 4. Updated `main.py` Lifespan

File: `src/knowledge_garden/main.py`

The lifespan function replaces `Config.from_yaml("config.yaml")` with `AppSettings()`. The nested config objects (`config.neo4j`, `config.together_ai`) are replaced by flat attribute access on `AppSettings`.

```python
from knowledge_garden.config import AppSettings

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = AppSettings()

    graph_store = Neo4jGraphStore(settings)
    await graph_store.initialize()

    provider = ...  # determined by business config or a default; see note below
    embedder: EmbeddingService
    if settings.hf_api_token is not None and provider == "huggingface":
        embedder = HuggingFaceEmbedder(settings)
    else:
        embedder = TogetherAIEmbedder(settings)

    app.state.settings = settings
    app.state.graph_store = graph_store
    app.state.embedder = embedder

    yield

    await embedder.close()
    await graph_store.close()
```

Note on provider selection in `main.py`: The FastAPI server no longer has access to `BusinessConfig` (it does not load YAML). The embedding provider for the server defaults to `"together"` unless `hf_api_token` is present, in which case the server may use `"huggingface"`. This is a deliberate simplification — the server is infrastructure-only. The exact provider-selection logic is preserved from the existing `main.py` but driven by `AppSettings` fields rather than `BusinessConfig.embedding.provider`.

### 4.1 Constructor Signature Changes for Services

`Neo4jGraphStore.__init__` currently accepts `(neo4j_config: Neo4jConfig, embedding_config: EmbeddingConfig)`. After this spec it must accept `AppSettings` directly OR the constructor must be called with keyword arguments derived from `AppSettings`. The approach is to call with keyword arguments extracted from `AppSettings`:

```python
graph_store = Neo4jGraphStore(
    neo4j_config=_neo4j_config_from_settings(settings),
    embedding_config=_embedding_config_from_settings(settings),
)
```

Where `_neo4j_config_from_settings` and `_embedding_config_from_settings` are private helper functions in `main.py` (not exported). They construct the legacy-compatible objects from `AppSettings` fields.

Similarly for embedders: `TogetherAIEmbedder` and `HuggingFaceEmbedder` constructors are called with helper-constructed objects. The service constructors themselves (`neo4j_store.py`, `together_embedder.py`, `hf_embedder.py`) are NOT modified — they still accept the same sub-model types. This limits blast radius.

The helpers in `main.py`:

```python
def _neo4j_config_from_settings(s: AppSettings) -> _Neo4jParams:
    ...

def _embedding_config_from_settings(s: AppSettings, dimension: int = 768) -> _EmbeddingParams:
    ...
```

These return simple namespace or dataclass objects with the same attribute names the service constructors expect. An alternative is to define thin dataclasses in `config.py` that the service constructors accept — but those are NOT the removed `Neo4jConfig`/`TogetherAIConfig` classes. They are private adapter types.

**Resolution for test-writer and executor:** To keep blast radius minimal, `main.py` and `cli.py` are updated to construct the existing service sub-models directly from `AppSettings` fields rather than refactoring the service constructors. This means `Neo4jConfig`, `TogetherAIConfig`, and `HuggingFaceConfig` sub-models are re-created as lightweight dataclasses or simple Pydantic models in `config.py` — but they are private (prefixed `_`) and not exported. Only `AppSettings` and `BusinessConfig` are part of the public API.

**Revised approach (simpler and lower risk):** Keep `Neo4jConfig`, `TogetherAIConfig`, and `HuggingFaceConfig` as internal Pydantic BaseModels in `config.py` (not exported from `__all__`, not imported by tests). `AppSettings` exposes two computed properties:

```python
@property
def neo4j(self) -> Neo4jConfig:
    return Neo4jConfig(
        uri=self.neo4j_uri,
        user=self.neo4j_user,
        password=self.neo4j_password,
        database=self.neo4j_database,
    )

@property
def together_ai(self) -> TogetherAIConfig:
    return TogetherAIConfig(
        api_key=self.together_api_key,
        base_url=self.together_base_url,
    )

@property
def hugging_face(self) -> HuggingFaceConfig | None:
    if self.hf_api_token is None:
        return None
    return HuggingFaceConfig(
        api_key=self.hf_api_token,
        base_url=self.hf_base_url,
    )
```

This means `main.py` and `cli.py` can call `settings.neo4j`, `settings.together_ai`, `settings.hugging_face` and pass them directly to service constructors without changes. The service constructors (`Neo4jGraphStore`, `TogetherAIEmbedder`, `HuggingFaceEmbedder`) remain untouched.

---

## 5. Updated `cli.py`

File: `src/knowledge_garden/cli.py`

The old `_load_config(path)` function is replaced by two functions:

```python
def _load_app_settings() -> AppSettings:
    """Instantiate AppSettings from environment / .env file.

    Raises pydantic_settings.ValidationError if TOGETHER_API_KEY is absent.
    """
    return AppSettings()


def _load_business_config(path: str) -> BusinessConfig:
    """Load BusinessConfig from a YAML file.

    Raises FileNotFoundError if the file does not exist.
    Raises yaml.YAMLError for malformed YAML.
    Raises pydantic.ValidationError for schema violations.
    """
    return BusinessConfig.from_yaml(path)
```

The `_make_embedder` function signature changes from `(config: Config)` to `(settings: AppSettings, business: BusinessConfig)`. It reads `business.embedding.provider` to determine the provider, and uses `settings.together_ai` or `settings.hugging_face` for credentials.

The `_make_graph_store` function signature changes from `(config: Config)` to `(settings: AppSettings, business: BusinessConfig)`. It reads `settings.neo4j` for connection and `business.embedding` for the embedding dimension.

All three CLI commands (`ingest`, `notes`, `status`) call `_load_app_settings()` and `_load_business_config(config_path)` at the start. The `notes` and `status` commands currently use the default `config.yaml` path; after this change they also accept a `--config` flag for consistency. The `ingest` command already has `--config`.

Updated command signatures:

```python
@app.command()
def ingest(
    vault_name: str,
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None: ...

@app.command()
def notes(
    vault: str | None = typer.Option(None, "--vault"),
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None: ...

@app.command()
def status(
    config_path: str = typer.Option("config.yaml", "--config"),
) -> None: ...
```

The `VaultConfig` import in `cli.py` changes from `from knowledge_garden.config import Config, VaultConfig` to `from knowledge_garden.config import AppSettings, BusinessConfig, VaultConfig`.

---

## 6. Removed Exports

The following names are no longer exported from `src/knowledge_garden/config.py`:

- `Config`
- `Neo4jConfig` (made internal / used only within `AppSettings` properties)
- `TogetherAIConfig` (made internal)
- `HuggingFaceConfig` (made internal)

The following names remain exported:

- `AppSettings`
- `BusinessConfig`
- `VaultConfig`
- `EmbeddingConfig`
- `LLMConfig`
- `ChunkingConfig`
- `LinkingConfig`
- `ExportConfig`

---

## 7. Test Specifications

File: `tests/test_config.py`

The existing test classes `TestConfigFromYaml` and `TestHuggingFaceConfig` are removed. They are replaced by the two classes below.

### 7.1 `TestAppSettings`

| Test name | Marker | Description | Inputs | Expected output | Edge cases |
|-----------|--------|-------------|--------|-----------------|------------|
| `test_app_settings_from_env` | unit | All required env vars set → `AppSettings()` succeeds, fields populated | `TOGETHER_API_KEY=test-key` in env | `settings.together_api_key == "test-key"` | — |
| `test_app_settings_defaults` | unit | Only required env var set → optional fields take their defaults | `TOGETHER_API_KEY=k` | `settings.neo4j_uri == "bolt://localhost:7687"`, `settings.together_base_url == "https://api.together.xyz/v1"`, `settings.hf_api_token is None`, `settings.app_host == "0.0.0.0"`, `settings.app_port == 8000` | — |
| `test_app_settings_missing_api_key` | unit | `TOGETHER_API_KEY` absent from env → `ValidationError` raised | No env vars set | `pytest.raises(ValidationError)` | Required field absent |
| `test_app_settings_neo4j_override` | unit | `NEO4J_URI` etc. set → fields populated | `NEO4J_URI=bolt://db:7687`, `NEO4J_USER=admin`, `NEO4J_PASSWORD=secret`, `NEO4J_DATABASE=prod` set in env | All four fields match env values | — |
| `test_app_settings_hf_optional` | unit | `HF_API_TOKEN` set → `hf_api_token` populated | `TOGETHER_API_KEY=k`, `HF_API_TOKEN=tok` | `settings.hf_api_token == "tok"` | — |
| `test_app_settings_hf_absent` | unit | `HF_API_TOKEN` not set → `hf_api_token` is `None` | `TOGETHER_API_KEY=k` only | `settings.hf_api_token is None` | — |
| `test_app_settings_neo4j_property` | unit | `settings.neo4j` returns object with correct attributes | `TOGETHER_API_KEY=k`, `NEO4J_URI=bolt://x:7687` | `settings.neo4j.uri == "bolt://x:7687"` | — |
| `test_app_settings_together_ai_property` | unit | `settings.together_ai` returns object with correct attributes | `TOGETHER_API_KEY=my-key` | `settings.together_ai.api_key == "my-key"` | — |
| `test_app_settings_hugging_face_property_none` | unit | `hf_api_token` is `None` → `settings.hugging_face` is `None` | `TOGETHER_API_KEY=k` | `settings.hugging_face is None` | — |
| `test_app_settings_hugging_face_property_set` | unit | `hf_api_token` is set → `settings.hugging_face.api_key` is populated | `TOGETHER_API_KEY=k`, `HF_API_TOKEN=tok` | `settings.hugging_face.api_key == "tok"` | — |
| `test_app_settings_reads_dotenv_file` | unit | `.env` file in working dir contains `TOGETHER_API_KEY` → settings reads it | Write temp `.env` with `TOGETHER_API_KEY=from-dotenv`; clear env var | `settings.together_api_key == "from-dotenv"` | dotenv file without explicit load_dotenv |
| `test_app_settings_env_overrides_dotenv` | unit | Env var set + `.env` file with different value → env var wins | `TOGETHER_API_KEY=from-env` in env; `.env` has `TOGETHER_API_KEY=from-file` | `settings.together_api_key == "from-env"` | Priority order |

Fixtures needed: `monkeypatch` (stdlib pytest), `tmp_path` (for dotenv file tests). The dotenv tests must temporarily change the working directory using `monkeypatch.chdir(tmp_path)` or provide the dotenv path explicitly via `AppSettings(_env_file=...)`.

Implementation note for test-writer: `AppSettings` reads the `.env` file relative to the working directory by default. Use `AppSettings(_env_file=str(tmp_path / ".env"))` in dotenv-specific tests to avoid interfering with the project's own `.env`.

### 7.2 `TestBusinessConfig`

| Test name | Marker | Description | Inputs | Expected output | Edge cases |
|-----------|--------|-------------|--------|-----------------|------------|
| `test_business_config_from_yaml_full` | unit | Load `config_business_full.yaml` → all fields populated | `tests/fixtures/config_business_full.yaml` | All sections match fixture values | — |
| `test_business_config_defaults` | unit | Load `config_business_minimal.yaml` (empty YAML or `{}`) → all defaults applied | `tests/fixtures/config_business_minimal.yaml` | `vaults == []`, `chunking.max_chunk_size == 1000`, `linking.threshold == 0.7`, etc. | — |
| `test_business_config_vault_list` | unit | YAML with 3 vaults → list of 3 `VaultConfig` | inline YAML in `tmp_path` | `len(config.vaults) == 3`, all names/paths match | — |
| `test_business_config_invalid_yaml` | unit | Malformed YAML → `yaml.YAMLError` | `tmp_path` file with `key: [unclosed` | `pytest.raises(yaml.YAMLError)` | Parse error |
| `test_business_config_missing_file` | unit | Non-existent path → `FileNotFoundError` | `tmp_path / "does_not_exist.yaml"` | `pytest.raises(FileNotFoundError)` | Missing file |
| `test_business_config_no_api_key` | unit | YAML with no API key → loads fine (no API key in BusinessConfig) | YAML with vaults section only | Config loads without error | BusinessConfig never requires API key |
| `test_business_config_chunking_override` | unit | YAML overrides `chunking.max_chunk_size` → value matches | YAML with `chunking.max_chunk_size: 500` | `config.chunking.max_chunk_size == 500` | — |
| `test_business_config_empty_yaml` | unit | Empty YAML file (`{}` or blank) → uses all defaults | Empty YAML | Same as defaults test | Empty file edge case |

Fixtures needed: `tmp_path`. New fixture files to create:
- `tests/fixtures/config_business_full.yaml` — all sections with non-default values to verify loading
- `tests/fixtures/config_business_minimal.yaml` — empty file or `{}` to verify defaults

### 7.3 `TestConfigExports`

| Test name | Marker | Description | Inputs | Expected output |
|-----------|--------|-------------|--------|-----------------|
| `test_config_does_not_export_old_Config` | unit | `Config` name not importable from `knowledge_garden.config` | `from knowledge_garden.config import Config` | `ImportError` raised |
| `test_config_exports_AppSettings` | unit | `AppSettings` importable from `knowledge_garden.config` | `from knowledge_garden.config import AppSettings` | No error |
| `test_config_exports_BusinessConfig` | unit | `BusinessConfig` importable from `knowledge_garden.config` | `from knowledge_garden.config import BusinessConfig` | No error |

---

## 8. Fixture Files

### `tests/fixtures/config_business_full.yaml`

Must contain non-default values for every section so tests can verify loading (not just defaults):

```yaml
vaults:
  - name: personal
    path: /home/user/vaults/personal
  - name: work
    path: /home/user/vaults/work

embedding:
  provider: together
  model: togethercomputer/m2-bert-80M-8k-retrieval
  dimension: 768
  batch_size: 64

llm:
  provider: together
  model: THUDM/glm-4-9b-chat
  max_tokens: 1024
  temperature: 0.3

chunking:
  max_chunk_size: 1000
  min_chunk_size: 100

linking:
  threshold: 0.7
  max_neighbors: 20

export:
  output_dir: ./output
```

### `tests/fixtures/config_business_minimal.yaml`

Empty content (or `{}`). BusinessConfig must load with all defaults.

---

## 9. `.env.example` Update

File: `.env.example` at the project root.

Add the new env var names to the example file:

```
# Copy to .env and fill in values before running docker compose up

# Required
TOGETHER_API_KEY=your_together_ai_api_key_here

# Optional (Neo4j — defaults shown)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=knowledge-garden
NEO4J_DATABASE=neo4j

# Optional (Together AI)
TOGETHER_BASE_URL=https://api.together.xyz/v1

# Optional (HuggingFace — only needed if embedding.provider = huggingface)
HF_API_TOKEN=
HF_BASE_URL=https://api-inference.huggingface.co

# Optional (FastAPI server)
APP_HOST=0.0.0.0
APP_PORT=8000
```

---

## 10. Dependencies

`pydantic-settings` is already listed in `pyproject.toml`. No new dependencies are introduced.

The explicit `from dotenv import load_dotenv` import added to `config.py` as a temporary patch is removed. `python-dotenv` remains a transitive dependency of `pydantic-settings` and is used internally, but it is never imported directly by application code.

---

## 11. What Does NOT Change

- `src/knowledge_garden/services/neo4j_store.py` — constructor signature unchanged
- `src/knowledge_garden/services/together_embedder.py` — constructor signature unchanged
- `src/knowledge_garden/services/hf_embedder.py` — constructor signature unchanged
- `src/knowledge_garden/models/` — unchanged
- `src/knowledge_garden/api/` — unchanged
- All other test files — unchanged
- `docker-compose.yml` and `Dockerfile` — no changes (config.yaml volume mount is removed separately if desired; that is out of scope for this spec)
