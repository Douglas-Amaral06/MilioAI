import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "production"
    auth_mode: Literal["jwt", "development"] = "jwt"
    dev_auth_token: str = Field(default="", repr=False)
    database_url: str = Field(repr=False)
    cors_origins: list[str] = ["http://127.0.0.1:5173"]
    jwt_issuer: str = ""
    jwt_audience: str = "authenticated"
    jwt_jwks_url: str = ""
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b-instruct"
    ollama_think: bool = False
    embedding_model: str = "nomic-embed-text-v2-moe:latest"
    embedding_dimensions: int = Field(default=768, ge=1, le=2000)
    embedding_query_prefix: str = "search_query: "
    embedding_document_prefix: str = "search_document: "
    ollama_timeout: float = Field(default=120, ge=1, le=600)
    generation_limit: int = Field(default=600, ge=32, le=2048)
    context_size: int = Field(default=4096, ge=2048, le=16384)
    history_chars: int = Field(default=4000, ge=100, le=16000)
    vt_kb_version: str = "vt-segunda-via-local-v1"
    active_kb_version: str = "test-v1"
    rag_top_k: int = Field(default=3, ge=1, le=10)
    rag_profile: str = "legacy"
    dev_document_scopes: list[str] = []
    rag_max_distance: float = Field(default=0.45, ge=0, le=1)
    storage_path: Path = Path("./private")
    upload_max_bytes: int = Field(default=5_242_880, ge=1024, le=20_971_520)

    @property
    def embedding_profile(self):
        if self.rag_profile == "legacy":
            return "legacy"
        return hashlib.sha256(
            json.dumps(
                {
                    "model": self.embedding_model,
                    "dimensions": self.embedding_dimensions,
                    "query": self.embedding_query_prefix,
                    "document": self.embedding_document_prefix,
                    "chunking": "vt-table-v1"
                    if self.rag_profile == "vt-table-v1"
                    else "sections-v3-contextual",
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    @model_validator(mode="after")
    def secure_modes(self):
        if self.dev_document_scopes and self.app_env != "development":
            raise ValueError("Development document scopes cannot be enabled outside development")
        if self.auth_mode == "development":
            if self.app_env != "development" or len(self.dev_auth_token) < 32:
                raise ValueError(
                    "Development auth requires development environment and a random token >=32 chars"
                )
        elif not self.jwt_issuer or not self.jwt_jwks_url:
            raise ValueError("JWT issuer and JWKS URL must be configured")
        if self.auth_mode == "jwt" and (
            not self.jwt_jwks_url.startswith("https://")
            or not self.jwt_issuer.startswith("https://")
        ):
            raise ValueError("JWT issuer and JWKS must use HTTPS")
        if "*" in self.cors_origins:
            raise ValueError("Explicit CORS origins required")
        # Remote model endpoints require a future explicit outbound-provider configuration.
        if urlparse(self.ollama_url).hostname not in {
            "localhost",
            "127.0.0.1",
            "host.docker.internal",
            "ollama",
        }:
            raise ValueError("Only local Ollama endpoints are enabled")
        return self


@lru_cache
def get_settings():
    return Settings()  # type: ignore[call-arg]  # Required fields are loaded from the environment.
