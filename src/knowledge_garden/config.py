"""Configuration module for Knowledge Garden.

Loads config from a YAML file with environment variable overrides.
TOGETHER_API_KEY env var maps to together_ai.api_key.
HF_API_TOKEN env var maps to hugging_face.api_key.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel


class VaultConfig(BaseModel):
    name: str
    path: str


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
    base_url: str = "https://api-inference.huggingface.co"


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


class Config(BaseModel):
    vaults: list[VaultConfig] = []
    neo4j: Neo4jConfig = Neo4jConfig()
    together_ai: TogetherAIConfig
    hugging_face: HuggingFaceConfig | None = None
    embedding: EmbeddingConfig = EmbeddingConfig()
    llm: LLMConfig = LLMConfig()
    chunking: ChunkingConfig = ChunkingConfig()
    linking: LinkingConfig = LinkingConfig()
    export: ExportConfig = ExportConfig()

    @classmethod
    def from_yaml(cls, path: str | Path) -> Config:
        """Load config from a YAML file, with env var overrides.

        The TOGETHER_API_KEY environment variable overrides together_ai.api_key.
        The HF_API_TOKEN environment variable overrides hugging_face.api_key.
        Raises yaml.YAMLError for malformed YAML.
        Raises pydantic.ValidationError if required fields are missing.
        """
        path = Path(path)
        load_dotenv(dotenv_path=path.parent / ".env", override=False)
        with path.open() as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}

        together_api_key = os.environ.get("TOGETHER_API_KEY")
        if together_api_key is not None:
            together_ai_section: dict[str, Any] = data.get("together_ai") or {}
            together_ai_section["api_key"] = together_api_key
            data["together_ai"] = together_ai_section

        neo4j_uri = os.environ.get("NEO4J_URI")
        if neo4j_uri is not None:
            neo4j_section: dict[str, Any] = data.get("neo4j") or {}
            neo4j_section["uri"] = neo4j_uri
            data["neo4j"] = neo4j_section

        hf_token = os.environ.get("HF_API_TOKEN")
        if hf_token is not None:
            hf_section: dict[str, Any] = data.get("hugging_face") or {}
            hf_section["api_key"] = hf_token
            data["hugging_face"] = hf_section

        return cls.model_validate(data)
