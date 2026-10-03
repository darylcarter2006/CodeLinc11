"""Runtime configuration, read from environment variables (or a local .env file)."""

from __future__ import annotations

from functools import lru_cache
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

    repository_backend: Literal["memory"] = "memory"
    ai_provider: Literal["stub"] = "stub"
    ai_timeout_seconds: float = 15.0

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
