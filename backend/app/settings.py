"""Runtime configuration, read from environment variables (or a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: Literal["local", "test", "dev", "demo", "prod"] = "local"
    log_level: str = "INFO"

    # Comma-separated in the environment, e.g. CORS_ORIGINS=http://localhost:5173
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    repository_backend: Literal["memory", "postgres"] = "memory"
    ai_provider: Literal["stub", "bedrock"] = "stub"
    ai_timeout_seconds: float = 15.0

    # --- PostgreSQL (required when repository_backend = "postgres") ---
    # Full async DSN: postgresql+asyncpg://user:pass@host:5432/dbname
    # In AWS this is constructed at startup from Secrets Manager; never hardcode it here.
    database_url: str | None = None
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    # CA bundle for verifying the server certificate (RDS: global-bundle.pem).
    # Leave unset for local Docker Postgres.
    db_ssl_root_cert: str | None = None

    # Bedrock — only required when ai_provider == "bedrock"
    bedrock_model_id: str = "us.amazon.nova-2-lite-v1:0"
    bedrock_region: str = "us-east-2"
    bedrock_guardrail_id: str | None = None
    bedrock_guardrail_version: str | None = None

    session_ttl_hours: int = Field(default=4, ge=1, le=72)
    session_turn_limit: int = Field(default=40, ge=1)
    message_max_chars: int = Field(default=2000, ge=1)
    max_body_bytes: int = Field(default=16 * 1024, ge=1024)
    message_history_turns: int = Field(default=10, ge=1)
    idempotency_ttl_hours: int = Field(default=24, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the postgresql+asyncpg:// scheme "
                "(e.g. postgresql+asyncpg://user:pass@host:5432/dbname)"
            )
        return value

    @field_validator("db_ssl_root_cert")
    @classmethod
    def _cert_exists(cls, value: str | None) -> str | None:
        if value is not None and not Path(value).is_file():
            raise ValueError(f"DB_SSL_ROOT_CERT file not found: {value}")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
