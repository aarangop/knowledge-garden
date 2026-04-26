# Tasks: Config Split

Tasks are ordered in TDD sequence: tests first (red), then implementation (green), then caller updates.

---

## Phase 1 — Test fixtures and new test file (red phase)

- [ ] Create `tests/fixtures/config_business_full.yaml` with all sections populated with non-default-verifiable values (contract section 8)
- [ ] Create `tests/fixtures/config_business_minimal.yaml` as an empty YAML file (`{}`) (contract section 8)
- [ ] Replace the contents of `tests/test_config.py`: remove `TestConfigFromYaml` and `TestHuggingFaceConfig` classes entirely; add `TestAppSettings`, `TestBusinessConfig`, and `TestConfigExports` classes with all test stubs (contract section 7)
- [ ] Verify all new tests in `tests/test_config.py` fail (red phase) — `uv run pytest tests/test_config.py -v -m unit`

---

## Phase 2 — Implement `AppSettings` and `BusinessConfig` (green phase)

- [ ] Rewrite `src/knowledge_garden/config.py`:
  - Remove `Config`, `Neo4jConfig`, `TogetherAIConfig`, `HuggingFaceConfig`, `from_yaml()` and all `os.environ.get` + `load_dotenv` logic (contract section 3.1, 6)
  - Keep `VaultConfig`, `EmbeddingConfig`, `LLMConfig`, `ChunkingConfig`, `LinkingConfig`, `ExportConfig` sub-models unchanged (contract section 3.2)
  - Add internal (non-exported) `Neo4jConfig`, `TogetherAIConfig`, `HuggingFaceConfig` as plain Pydantic BaseModels for use by `AppSettings` properties only (contract section 4, revised approach)
  - Implement `AppSettings(BaseSettings)` with all fields and `model_config` (contract section 2)
  - Implement `AppSettings.neo4j`, `AppSettings.together_ai`, `AppSettings.hugging_face` computed properties (contract section 4, revised approach)
  - Implement `BusinessConfig(BaseModel)` with all fields and `from_yaml()` class method (contract section 3)
- [ ] Verify `TestAppSettings` and `TestBusinessConfig` tests pass: `uv run pytest tests/test_config.py -v -m unit`
- [ ] Verify `TestConfigExports` tests pass (i.e. `Config` raises `ImportError`, `AppSettings` and `BusinessConfig` import cleanly)
- [ ] Run full unit test suite to confirm no regressions: `uv run pytest tests/ -v -m unit`

---

## Phase 3 — Update `main.py` (green phase)

- [ ] Update `src/knowledge_garden/main.py`:
  - Change import from `from knowledge_garden.config import Config` to `from knowledge_garden.config import AppSettings` (contract section 4)
  - Replace `Config.from_yaml("config.yaml")` with `settings = AppSettings()` in the lifespan function (contract section 4)
  - Replace `config.neo4j` with `settings.neo4j`, `config.together_ai` with `settings.together_ai`, `config.hugging_face` with `settings.hugging_face` throughout (contract section 4)
  - Replace `app.state.config = config` with `app.state.settings = settings` (contract section 4)
  - Remove any remaining references to the old `Config` class
- [ ] Verify `tests/test_api.py` still passes: `uv run pytest tests/test_api.py -v -m unit`

---

## Phase 4 — Update `cli.py` (green phase)

- [ ] Update `src/knowledge_garden/cli.py`:
  - Change import from `from knowledge_garden.config import Config, VaultConfig` to `from knowledge_garden.config import AppSettings, BusinessConfig, VaultConfig` (contract section 5)
  - Remove `_load_config()` function (contract section 5)
  - Add `_load_app_settings() -> AppSettings` function (contract section 5)
  - Add `_load_business_config(path: str) -> BusinessConfig` function (contract section 5)
  - Update `_make_embedder` signature to `(settings: AppSettings, business: BusinessConfig)` — read `business.embedding.provider` for provider selection, `settings.together_ai` or `settings.hugging_face` for credentials (contract section 5)
  - Update `_make_graph_store` signature to `(settings: AppSettings, business: BusinessConfig)` — pass `settings.neo4j` and `business.embedding` to the constructor (contract section 5)
  - Update `ingest` command: call `_load_app_settings()` and `_load_business_config(config_path)`, pass both to `_make_embedder` and `_make_graph_store` (contract section 5)
  - Update `notes` command: add `config_path: str = typer.Option("config.yaml", "--config")` parameter, call both loaders (contract section 5)
  - Update `status` command: add `config_path: str = typer.Option("config.yaml", "--config")` parameter, call both loaders (contract section 5)
  - Remove any remaining references to the old `Config` class
- [ ] Verify `uv run pytest tests/ -v -m unit` passes with no regressions

---

## Phase 5 — Update `.env.example`

- [ ] Update `.env.example` at the project root to include all `AppSettings` env vars with comments and defaults as specified in contract section 9

---

## Phase 6 — Final verification

- [ ] Run full unit test suite: `uv run pytest tests/ -v -m unit` — all pass
- [ ] Run integration test suite: `uv run pytest tests/ -v -m integration` — all pass (requires running Neo4j)
- [ ] Confirm no import of `Config` remains anywhere in `src/` or `tests/`: `grep -r "from knowledge_garden.config import.*Config[^s]" src/ tests/` returns no matches
- [ ] Confirm `AppSettings` and `BusinessConfig` are the only config types imported by `main.py` and `cli.py` respectively
- [ ] Run `uv run ruff check src/ tests/` — no lint errors
- [ ] Run `uv run mypy src/` — no type errors
