"""Tests for config module — contract: specifications/01_foundation/contract.md, section 1
and specifications/02_ingestion/contract.md, section 3.4"""
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from knowledge_garden.config import Config, VaultConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestConfigFromYaml:
    """Contract section 1.2 — loading and validation of Config from YAML files."""

    @pytest.mark.unit
    def test_config_from_yaml(self):
        """Contract: Load config_valid.yaml, verify all fields populated."""
        config = Config.from_yaml(FIXTURES_DIR / "config_valid.yaml")

        # Vaults
        assert len(config.vaults) == 2
        assert config.vaults[0].name == "personal"
        assert config.vaults[0].path == "/home/user/vaults/personal"
        assert config.vaults[1].name == "work"
        assert config.vaults[1].path == "/home/user/vaults/work"

        # Neo4j
        assert config.neo4j.uri == "bolt://localhost:7687"
        assert config.neo4j.user == "neo4j"
        assert config.neo4j.password == "knowledge-garden"
        assert config.neo4j.database == "neo4j"

        # Together AI
        assert config.together_ai.api_key == "test-api-key-valid"
        assert config.together_ai.base_url == "https://api.together.xyz/v1"

        # Embedding
        assert config.embedding.provider == "together"
        assert config.embedding.model == "togethercomputer/m2-bert-80M-8k-retrieval"
        assert config.embedding.dimension == 768
        assert config.embedding.batch_size == 64

        # LLM
        assert config.llm.provider == "together"
        assert config.llm.model == "THUDM/glm-4-9b-chat"
        assert config.llm.max_tokens == 1024
        assert config.llm.temperature == 0.3

        # Chunking
        assert config.chunking.max_chunk_size == 1000
        assert config.chunking.min_chunk_size == 100

        # Linking
        assert config.linking.threshold == 0.7
        assert config.linking.max_neighbors == 20

        # Export
        assert config.export.output_dir == "./output"

    @pytest.mark.unit
    def test_config_env_override(self, monkeypatch):
        """Contract: Set TOGETHER_API_KEY env var, verify it populates together_ai.api_key."""
        monkeypatch.setenv("TOGETHER_API_KEY", "env-injected-key")
        config = Config.from_yaml(FIXTURES_DIR / "config_minimal.yaml")

        assert config.together_ai.api_key == "env-injected-key"

    @pytest.mark.unit
    def test_config_defaults(self):
        """Contract: Load config_minimal.yaml (only required fields), verify defaults applied."""
        config = Config.from_yaml(FIXTURES_DIR / "config_minimal.yaml")

        # Vaults defaults to empty list
        assert config.vaults == []

        # Neo4j defaults
        assert config.neo4j.uri == "bolt://localhost:7687"
        assert config.neo4j.user == "neo4j"
        assert config.neo4j.password == "knowledge-garden"
        assert config.neo4j.database == "neo4j"

        # Together AI base_url default
        assert config.together_ai.base_url == "https://api.together.xyz/v1"

        # Embedding defaults
        assert config.embedding.provider == "together"
        assert config.embedding.model == "togethercomputer/m2-bert-80M-8k-retrieval"
        assert config.embedding.dimension == 768
        assert config.embedding.batch_size == 64

        # LLM defaults
        assert config.llm.provider == "together"
        assert config.llm.model == "THUDM/glm-4-9b-chat"
        assert config.llm.max_tokens == 1024
        assert config.llm.temperature == 0.3

        # Chunking defaults
        assert config.chunking.max_chunk_size == 1000
        assert config.chunking.min_chunk_size == 100

        # Linking defaults
        assert config.linking.threshold == 0.7
        assert config.linking.max_neighbors == 20

        # Export defaults
        assert config.export.output_dir == "./output"

    @pytest.mark.unit
    def test_config_missing_api_key(self, monkeypatch, tmp_path):
        """Edge case: Omit API key from both YAML and env → ValidationError."""
        # Ensure env var is absent
        monkeypatch.delenv("TOGETHER_API_KEY", raising=False)

        # YAML with no together_ai section at all
        yaml_file = tmp_path / "config_no_key.yaml"
        yaml_file.write_text("vaults: []\n")

        with pytest.raises(ValidationError):
            Config.from_yaml(yaml_file)

    @pytest.mark.unit
    def test_config_invalid_yaml(self, tmp_path):
        """Edge case: Malformed YAML file → clear error raised."""
        bad_yaml = tmp_path / "bad_config.yaml"
        bad_yaml.write_text("together_ai:\n  api_key: [unclosed bracket\n  bad: : :\n")

        with pytest.raises(yaml.YAMLError):
            Config.from_yaml(bad_yaml)

    @pytest.mark.unit
    def test_config_vault_list(self, tmp_path):
        """Contract: YAML with 3 vaults → list of 3 VaultConfig objects."""
        yaml_content = """
vaults:
  - name: vault-one
    path: /vaults/one
  - name: vault-two
    path: /vaults/two
  - name: vault-three
    path: /vaults/three
together_ai:
  api_key: test-api-key-vaults
"""
        yaml_file = tmp_path / "config_three_vaults.yaml"
        yaml_file.write_text(yaml_content)

        config = Config.from_yaml(yaml_file)

        assert len(config.vaults) == 3
        assert all(isinstance(v, VaultConfig) for v in config.vaults)
        assert config.vaults[0].name == "vault-one"
        assert config.vaults[1].name == "vault-two"
        assert config.vaults[2].name == "vault-three"
        assert config.vaults[0].path == "/vaults/one"
        assert config.vaults[1].path == "/vaults/two"
        assert config.vaults[2].path == "/vaults/three"


class TestHuggingFaceConfig:
    """Contract section 3.4 — HuggingFaceConfig additions and env var injection."""

    @pytest.mark.unit
    def test_config_hf_section_optional(self, monkeypatch, tmp_path):
        """Contract: YAML with no hugging_face key and HF_API_TOKEN not set →
        config.hugging_face is None.
        """
        monkeypatch.delenv("HF_API_TOKEN", raising=False)

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("together_ai:\n  api_key: test-key\n")

        config = Config.from_yaml(yaml_file)

        assert config.hugging_face is None

    @pytest.mark.unit
    def test_config_hf_env_token_override(self, monkeypatch, tmp_path):
        """Contract: HF_API_TOKEN set in env, no hugging_face YAML section → api_key injected,
        base_url is default.
        """
        monkeypatch.setenv("HF_API_TOKEN", "tok123")

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("together_ai:\n  api_key: test-key\n")

        config = Config.from_yaml(yaml_file)

        assert config.hugging_face is not None
        assert config.hugging_face.api_key == "tok123"
        assert config.hugging_face.base_url == "https://api-inference.huggingface.co"

    @pytest.mark.unit
    def test_config_hf_env_token_merges(self, monkeypatch, tmp_path):
        """Contract: HF_API_TOKEN set + hugging_face.base_url in YAML → api_key injected,
        base_url preserved.
        """
        monkeypatch.setenv("HF_API_TOKEN", "tok456")

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "together_ai:\n  api_key: test-key\n"
            "hugging_face:\n  base_url: https://custom.hf.co\n"
        )

        config = Config.from_yaml(yaml_file)

        assert config.hugging_face is not None
        assert config.hugging_face.api_key == "tok456"
        assert config.hugging_face.base_url == "https://custom.hf.co"
