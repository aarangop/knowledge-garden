"""Configuration module for Knowledge Garden.

Public API:
  AppSettings  — reads from environment variables / .env file (no YAML)
  BusinessConfig — reads from a YAML file (CLI only, not used by FastAPI server)

Internal (not exported, but importable by service constructors):
  Neo4jConfig, TogetherAIConfig, HuggingFaceConfig — thin Pydantic models used
  as adapters between AppSettings and the unchanged service constructors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "AppSettings",
    "BusinessConfig",
    "VaultConfig",
    "EmbeddingConfig",
    "LLMConfig",
    "ChunkingConfig",
    "LinkingConfig",
    "DedupConfig",
    "ExportConfig",
    "SearchConfig",
]

# ---------------------------------------------------------------------------
# Internal adapter models (not part of public API — no entry in __all__)
# Used by service constructors which accept these specific types.
# ---------------------------------------------------------------------------


class Neo4jConfig(BaseModel):
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "knowledge-garden"
    database: str = "neo4j"


class TogetherAIConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.together.xyz/v1"


class HuggingFaceConfig(BaseModel):
    api_key: str = ""


# ---------------------------------------------------------------------------
# AppSettings — reads from env vars and .env file, no YAML
# ---------------------------------------------------------------------------


class AppSettings(BaseSettings):
    """Application settings read from environment variables and/or a .env file.

    TOGETHER_API_KEY is the only required field. All other fields have defaults.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Together AI
    together_api_key: str = Field(default=..., description="API key for Together AI")
    together_base_url: str = "https://api.together.xyz/v1"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "knowledge-garden"
    neo4j_database: str = "neo4j"

    # HuggingFace (optional)
    hf_api_token: str | None = None

    # FastAPI server (optional — only used by CLI/compose startup)
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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
        )


# ---------------------------------------------------------------------------
# BusinessConfig sub-models (public — in __all__)
# ---------------------------------------------------------------------------


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


class DedupConfig(BaseModel):
    threshold: float = 0.95


class ExportConfig(BaseModel):
    output_dir: str = "./output"


class SearchConfig(BaseModel):
    search_limit: int = 10


# ---------------------------------------------------------------------------
# BusinessConfig — loaded from YAML by the CLI; not used by FastAPI server
# ---------------------------------------------------------------------------


class BusinessConfig(BaseModel):
    """Business / domain configuration loaded from a YAML file.

    The FastAPI server does not import or instantiate BusinessConfig.
    """

    vaults: list[VaultConfig] = []
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    linking: LinkingConfig = LinkingConfig()
    dedup: DedupConfig = DedupConfig()
    export: ExportConfig = ExportConfig()
    search: SearchConfig = SearchConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> BusinessConfig:
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
            data: dict[str, Any] = yaml.safe_load(f) or {}
        return cls.model_validate(data)
