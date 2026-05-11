"""Tests for config module — contract: specifications/04_config_split/contract.md"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestAppSettings:
    """Contract section 7.1 — AppSettings reads from env vars and .env file."""

    @pytest.mark.unit
    def test_app_settings_from_env(self, monkeypatch):
        """Contract: All required env vars set → AppSettings() succeeds, fields populated."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.together_api_key == "test-key"

    @pytest.mark.unit
    def test_app_settings_defaults(self, monkeypatch):
        """Contract: Only required env var set → optional fields take their defaults."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.delenv("TOGETHER_BASE_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        monkeypatch.delenv("NEO4J_DATABASE", raising=False)
        monkeypatch.delenv("HF_API_TOKEN", raising=False)
        monkeypatch.delenv("HF_BASE_URL", raising=False)
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_PORT", raising=False)
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.neo4j_uri == "bolt://localhost:7687"
        assert settings.together_base_url == "https://api.together.xyz/v1"
        assert settings.hf_api_token is None
        assert settings.app_host == "0.0.0.0"
        assert settings.app_port == 8000

    @pytest.mark.unit
    def test_app_settings_missing_api_key(self, monkeypatch):
        """Edge case: TOGETHER_API_KEY absent from env → ValidationError raised."""
        from knowledge_garden.config import AppSettings

        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            AppSettings(_env_file="")  # type: ignore[call-arg]

    @pytest.mark.unit
    def test_app_settings_neo4j_override(self, monkeypatch):
        """Contract: NEO4J_URI etc. set → fields populated with env var values."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("NEO4J_URI", "bolt://db:7687")
        monkeypatch.setenv("NEO4J_USER", "admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")
        monkeypatch.setenv("NEO4J_DATABASE", "prod")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.neo4j_uri == "bolt://db:7687"
        assert settings.neo4j_user == "admin"
        assert settings.neo4j_password == "secret"
        assert settings.neo4j_database == "prod"

    @pytest.mark.unit
    def test_app_settings_hf_optional(self, monkeypatch):
        """Contract: HF_API_TOKEN set → hf_api_token field populated."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("HF_API_TOKEN", "tok")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.hf_api_token == "tok"
        assert not hasattr(settings, "hf_base_url")

    @pytest.mark.unit
    def test_app_settings_hf_base_url_ignored(self, monkeypatch):
        """Contract: HF_BASE_URL in env is silently ignored (extra='ignore')."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("HF_BASE_URL", "https://custom.co")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert not hasattr(settings, "hf_base_url")

    @pytest.mark.unit
    def test_app_settings_hf_absent(self, monkeypatch):
        """Contract: HF_API_TOKEN not set → hf_api_token is None."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.delenv("HF_API_TOKEN", raising=False)
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.hf_api_token is None

    @pytest.mark.unit
    def test_app_settings_neo4j_property(self, monkeypatch):
        """Contract: settings.neo4j returns object with correct attributes."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("NEO4J_URI", "bolt://x:7687")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.neo4j.uri == "bolt://x:7687"

    @pytest.mark.unit
    def test_app_settings_together_ai_property(self, monkeypatch):
        """Contract: settings.together_ai returns object with correct attributes."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "my-key")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.together_ai.api_key == "my-key"

    @pytest.mark.unit
    def test_app_settings_hugging_face_property_none(self, monkeypatch):
        """Contract: hf_api_token is None → settings.hugging_face is None."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.delenv("HF_API_TOKEN", raising=False)
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.hugging_face is None

    @pytest.mark.unit
    def test_app_settings_hugging_face_property_set(self, monkeypatch):
        """Contract: hf_api_token set → hugging_face.api_key populated, no base_url."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("HF_API_TOKEN", "tok")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert settings.hugging_face is not None
        assert settings.hugging_face.api_key == "tok"
        assert not hasattr(settings.hugging_face, "base_url")

    @pytest.mark.unit
    def test_app_settings_reads_dotenv_file(self, monkeypatch, tmp_path):
        """Contract: .env file contains TOGETHER_API_KEY → settings reads it without explicit load_dotenv."""
        from knowledge_garden.config import AppSettings

        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("TOGETHER_API_KEY=from-dotenv\n")
        settings = AppSettings(_env_file=str(env_file))  # type: ignore[call-arg]
        assert settings.together_api_key == "from-dotenv"

    @pytest.mark.unit
    def test_app_settings_env_overrides_dotenv(self, monkeypatch, tmp_path):
        """Contract: Env var set + .env file with different value → env var wins (higher priority)."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "from-env")
        env_file = tmp_path / ".env"
        env_file.write_text("TOGETHER_API_KEY=from-file\n")
        settings = AppSettings(_env_file=str(env_file))  # type: ignore[call-arg]
        assert settings.together_api_key == "from-env"


class TestBusinessConfig:
    """Contract section 7.2 — BusinessConfig loads from YAML, no API key required."""

    @pytest.mark.unit
    def test_business_config_from_yaml_full(self):
        """Contract: Load config_business_full.yaml → all fields populated with fixture values."""
        from knowledge_garden.config import BusinessConfig, VaultConfig

        config = BusinessConfig.from_yaml(FIXTURES_DIR / "config_business_full.yaml")

        assert len(config.vaults) == 2
        assert isinstance(config.vaults[0], VaultConfig)
        assert config.vaults[0].name == "personal"
        assert config.vaults[0].path == "/home/user/vaults/personal"
        assert config.vaults[1].name == "work"
        assert config.vaults[1].path == "/home/user/vaults/work"

        assert config.embedding.provider == "together"
        assert config.embedding.model == "togethercomputer/m2-bert-80M-8k-retrieval"
        assert config.embedding.dimension == 768
        assert config.embedding.batch_size == 64

        assert config.llm.provider == "together"
        assert config.llm.model == "THUDM/glm-4-9b-chat"
        assert config.llm.max_tokens == 1024
        assert config.llm.temperature == 0.3

        assert config.chunking.max_chunk_size == 1000
        assert config.chunking.min_chunk_size == 100

        assert config.linking.threshold == 0.7
        assert config.linking.max_neighbors == 20

        assert config.dedup.threshold == 0.95

        assert config.export.output_dir == "./output"

    @pytest.mark.unit
    def test_business_config_defaults(self):
        """Contract: Load config_business_minimal.yaml (empty YAML) → all defaults applied."""
        from knowledge_garden.config import BusinessConfig

        config = BusinessConfig.from_yaml(FIXTURES_DIR / "config_business_minimal.yaml")

        assert config.vaults == []
        assert config.chunking.max_chunk_size == 1000
        assert config.chunking.min_chunk_size == 100
        assert config.linking.threshold == 0.7
        assert config.linking.max_neighbors == 20
        assert config.embedding.provider == "together"
        assert config.embedding.dimension == 768
        assert config.llm.max_tokens == 1024
        assert config.export.output_dir == "./output"
        assert config.dedup.threshold == 0.95

    @pytest.mark.unit
    def test_dedup_config_model(self):
        """Contract: DedupConfig has threshold field with default 0.95."""
        from knowledge_garden.config import DedupConfig

        cfg = DedupConfig()
        assert cfg.threshold == 0.95

    @pytest.mark.unit
    def test_dedup_config_custom_threshold(self, tmp_path):
        """Contract: YAML with dedup.threshold: 0.8 → value matches override."""
        from knowledge_garden.config import BusinessConfig

        yaml_content = "dedup:\n  threshold: 0.8\n"
        yaml_file = tmp_path / "config_dedup.yaml"
        yaml_file.write_text(yaml_content)

        config = BusinessConfig.from_yaml(yaml_file)

        assert config.dedup.threshold == 0.8

    @pytest.mark.unit
    def test_business_config_vault_list(self, tmp_path):
        """Contract: YAML with 3 vaults → list of 3 VaultConfig objects with correct names/paths."""
        from knowledge_garden.config import BusinessConfig, VaultConfig

        yaml_content = """\
vaults:
  - name: vault-one
    path: /vaults/one
  - name: vault-two
    path: /vaults/two
  - name: vault-three
    path: /vaults/three
"""
        yaml_file = tmp_path / "config_three_vaults.yaml"
        yaml_file.write_text(yaml_content)

        config = BusinessConfig.from_yaml(yaml_file)

        assert len(config.vaults) == 3
        assert all(isinstance(v, VaultConfig) for v in config.vaults)
        assert config.vaults[0].name == "vault-one"
        assert config.vaults[0].path == "/vaults/one"
        assert config.vaults[1].name == "vault-two"
        assert config.vaults[1].path == "/vaults/two"
        assert config.vaults[2].name == "vault-three"
        assert config.vaults[2].path == "/vaults/three"

    @pytest.mark.unit
    def test_business_config_invalid_yaml(self, tmp_path):
        """Edge case: Malformed YAML file → yaml.YAMLError raised."""
        from knowledge_garden.config import BusinessConfig

        bad_yaml = tmp_path / "bad_config.yaml"
        bad_yaml.write_text("key: [unclosed\n")

        with pytest.raises(yaml.YAMLError):
            BusinessConfig.from_yaml(bad_yaml)

    @pytest.mark.unit
    def test_business_config_missing_file(self, tmp_path):
        """Edge case: Non-existent path → FileNotFoundError raised."""
        from knowledge_garden.config import BusinessConfig

        with pytest.raises(FileNotFoundError):
            BusinessConfig.from_yaml(tmp_path / "does_not_exist.yaml")

    @pytest.mark.unit
    def test_business_config_no_api_key(self, tmp_path):
        """Contract: YAML with vaults section only and no API key → loads fine (BusinessConfig never requires API key)."""
        from knowledge_garden.config import BusinessConfig

        yaml_content = """\
vaults:
  - name: my-vault
    path: /vaults/mine
"""
        yaml_file = tmp_path / "config_no_key.yaml"
        yaml_file.write_text(yaml_content)

        config = BusinessConfig.from_yaml(yaml_file)

        assert len(config.vaults) == 1
        assert config.vaults[0].name == "my-vault"

    @pytest.mark.unit
    def test_business_config_chunking_override(self, tmp_path):
        """Contract: YAML overrides chunking.max_chunk_size → value matches the override."""
        from knowledge_garden.config import BusinessConfig

        yaml_content = "chunking:\n  max_chunk_size: 500\n"
        yaml_file = tmp_path / "config_chunking.yaml"
        yaml_file.write_text(yaml_content)

        config = BusinessConfig.from_yaml(yaml_file)

        assert config.chunking.max_chunk_size == 500

    @pytest.mark.unit
    def test_business_config_empty_yaml(self, tmp_path):
        """Edge case: Completely empty YAML file → uses all defaults (equivalent to minimal)."""
        from knowledge_garden.config import BusinessConfig

        yaml_file = tmp_path / "config_empty.yaml"
        yaml_file.write_text("")

        config = BusinessConfig.from_yaml(yaml_file)

        assert config.vaults == []
        assert config.chunking.max_chunk_size == 1000
        assert config.linking.threshold == 0.7
        assert config.export.output_dir == "./output"


class TestConfigExports:
    """Contract section 7.3 — public API of knowledge_garden.config."""

    @pytest.mark.unit
    def test_config_does_not_export_old_Config(self):
        """Contract: Config name is not importable from knowledge_garden.config (removed)."""
        with pytest.raises(ImportError):
            from knowledge_garden.config import Config  # noqa: F401

    @pytest.mark.unit
    def test_config_exports_AppSettings(self):
        """Contract: AppSettings is importable from knowledge_garden.config."""
        from knowledge_garden.config import AppSettings  # noqa: F401
        assert AppSettings is not None

    @pytest.mark.unit
    def test_config_exports_BusinessConfig(self):
        """Contract: BusinessConfig is importable from knowledge_garden.config."""
        from knowledge_garden.config import BusinessConfig  # noqa: F401
        assert BusinessConfig is not None

    @pytest.mark.unit
    def test_hugging_face_config_no_base_url(self):
        """Contract: HuggingFaceConfig has no base_url field (removed in spec 05)."""
        from knowledge_garden.config import HuggingFaceConfig

        assert set(HuggingFaceConfig.model_fields.keys()) == {"api_key"}
        cfg = HuggingFaceConfig(api_key="k")
        assert not hasattr(cfg, "base_url")

    @pytest.mark.unit
    def test_app_settings_hugging_face_property_no_base_url(self, monkeypatch):
        """Contract: settings.hugging_face returns HuggingFaceConfig without base_url."""
        from knowledge_garden.config import AppSettings

        monkeypatch.setenv("TOGETHER_API_KEY", "k")
        monkeypatch.setenv("HF_API_TOKEN", "tok")
        settings = AppSettings(_env_file="")  # type: ignore[call-arg]
        assert not hasattr(settings.hugging_face, "base_url")

    @pytest.mark.unit
    def test_dedup_config_exported(self):
        """Contract: DedupConfig is importable from knowledge_garden.config."""
        from knowledge_garden.config import DedupConfig
        assert DedupConfig is not None

    @pytest.mark.unit
    def test_search_config_exported(self):
        """Contract: SearchConfig is importable from knowledge_garden.config."""
        from knowledge_garden.config import SearchConfig  # noqa: F401
        assert SearchConfig is not None


class TestSearchConfig:
    """Contract section 5 — SearchConfig and BusinessConfig.search field (spec 10)."""

    @pytest.mark.unit
    def test_search_config_default(self):
        """Contract: BusinessConfig() without YAML → business.search.search_limit == 10."""
        from knowledge_garden.config import BusinessConfig

        business = BusinessConfig()

        assert hasattr(business, "search"), "BusinessConfig missing 'search' field"
        assert business.search.search_limit == 10

    @pytest.mark.unit
    def test_search_config_from_yaml(self, tmp_path):
        """Contract: YAML with search.search_limit: 25 → business.search.search_limit == 25."""
        from knowledge_garden.config import BusinessConfig

        yaml_content = "search:\n  search_limit: 25\n"
        yaml_file = tmp_path / "config_search.yaml"
        yaml_file.write_text(yaml_content)

        business = BusinessConfig.from_yaml(yaml_file)

        assert business.search.search_limit == 25
