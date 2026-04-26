# Roadmap: Config Split

## 1. Define `AppSettings`

Replace infrastructure fields in the old `Config` with a `pydantic_settings.BaseSettings` subclass. Fields: `TOGETHER_API_KEY`, `TOGETHER_BASE_URL`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `HF_API_TOKEN` (optional), `HF_BASE_URL`, `APP_HOST`, `APP_PORT`. Settings reads from environment variables and a `.env` file automatically — no manual `os.environ.get` calls.

**Done when:** `AppSettings()` instantiates from env vars, raises `ValidationError` if required fields are absent, and reads from a `.env` file without explicit `load_dotenv()` calls.

## 2. Define `BusinessConfig`

Replace user-facing fields in the old `Config` with a plain `pydantic.BaseModel` subclass and a `from_yaml(path)` class method. Fields: `vaults`, `chunking`, `linking`, `export`, `embedding`, `llm`. The nested sub-models (`VaultConfig`, `ChunkingConfig`, `LinkingConfig`, `ExportConfig`, `EmbeddingConfig`, `LLMConfig`) are preserved with the same field names and defaults. The `from_yaml()` method raises `yaml.YAMLError` for malformed YAML and `pydantic.ValidationError` for schema violations.

**Done when:** `BusinessConfig.from_yaml("config.yaml")` loads all user-facing settings from a YAML file, with all existing defaults preserved.

## 3. Remove the old `Config` class

Delete `Config`, `Neo4jConfig`, `TogetherAIConfig`, `HuggingFaceConfig`, `from_yaml()` and all manual env-override logic from `config.py`. The file exports only `AppSettings`, `BusinessConfig`, and the shared sub-models.

**Done when:** The old `Config` class and `from_yaml()` no longer exist in `config.py`. No other module imports them.

## 4. Update `main.py`

Replace `Config.from_yaml("config.yaml")` in the lifespan with `AppSettings()`. Wire `Neo4jGraphStore` and the embedders using fields drawn from `AppSettings` instead of the old nested config objects. The app must start with no YAML file present.

**Done when:** `main.py` imports only `AppSettings` from config, and the lifespan no longer references `Config` or YAML loading.

## 5. Update `cli.py`

Replace `_load_config()` with two separate loaders: `_load_app_settings()` returning `AppSettings()` and `_load_business_config(path)` returning `BusinessConfig.from_yaml(path)`. The `ingest`, `notes`, and `status` commands load both. Infrastructure objects (`Neo4jGraphStore`, embedders) are built from `AppSettings`; business logic (vault selection, chunking) uses `BusinessConfig`.

**Done when:** All three CLI commands work with the split config. No command references the old `Config` class.

## 6. Replace config tests

Remove all tests in `tests/test_config.py` that reference the old `Config` class and write new tests for `AppSettings` and `BusinessConfig` as specified in the contract.

**Done when:** `tests/test_config.py` contains only tests for `AppSettings` and `BusinessConfig`. All tests pass. No references to the old `Config` class remain.
