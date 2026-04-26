# Intent: Config Split

The project currently uses a single `Config` class that loads both secrets and business settings from a YAML file with ad-hoc environment variable overrides bolted on top. This conflates two distinct concerns: infrastructure secrets (API keys, database credentials) and user-facing business settings (vault paths, chunking parameters). The ad-hoc env var patching in `Config.from_yaml()` is brittle and unnecessary once `pydantic-settings` handles it natively.

This phase separates those concerns cleanly into two types:

**`AppSettings`** holds infrastructure secrets and deployment parameters — the things a Docker container needs to run. It extends `pydantic_settings.BaseSettings` and reads exclusively from environment variables and a `.env` file. No YAML is involved. No secret ever needs to be baked into an image or mounted as a file.

**`BusinessConfig`** holds user-facing settings that vary per knowledge garden deployment — vault definitions, chunking parameters, similarity thresholds, export path, and model choices. It is a plain `pydantic.BaseModel` loaded from a `config.yaml` file. Only the CLI uses it. The FastAPI server does not load or depend on it.

The old `Config` class, its `from_yaml()` method, the manual `os.environ.get` patching, and the ad-hoc `load_dotenv()` call are all removed. `BaseSettings` handles dotenv loading natively.

Success looks like: the FastAPI server starts with only environment variables set (no YAML file mounted or present), and the CLI accepts a `--config path/to/config.yaml` flag to load business settings. The Docker image does not mount `config.yaml`. Existing callers in `main.py` and `cli.py` are updated to use the new types. All existing config tests are replaced with tests for the new classes.

Open question: `HuggingFaceConfig` was previously a section in `Config`. It holds an API key (infrastructure) and a base URL (infrastructure). Under this split it belongs in `AppSettings`. The HuggingFace provider path in `main.py` and `cli.py` is preserved but wired through `AppSettings`.
