"""Runtime configuration, read from environment variables (or a local .env file)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    # "stub": no model (the AI endpoints return 503 and the front end uses its fallbacks).
    # "anthropic": Claude through the Anthropic API; requires ANTHROPIC_API_KEY.
    ai_provider: Literal["stub", "anthropic"] = "stub"
    # Seconds to wait for a reply to start (with thinking, the first text can take a moment).
    ai_timeout_seconds: float = 30.0
    # Never log or return this. Locally it comes from .env; on ECS from Secrets Manager.
    anthropic_api_key: SecretStr | None = None
    # "fast" handles onboarding extraction, "smart" the Chat tab. Both default to Claude Sonnet.
    ai_model_fast: str = "claude-sonnet-5-5"
    ai_model_smart: str = "claude-sonnet-5-5"
    ai_effort: Literal["low", "medium", "high"] = "low"
    # Server-side refusal fallbacks (Claude API only): if Claude declines a request in a
    # category Anthropic can route, the API retries it on another model in the same call.
    ai_refusal_fallbacks: bool = True
    # Per client IP, across /v1/ai/extract and /v1/ai/chat combined.
    ai_rate_limit_per_minute: int = Field(default=20, ge=1)
    # Across all visitors (per running task): a hard ceiling on model calls, and so on cost,
    # even if requests come from many IP addresses.
    ai_global_rate_limit_per_minute: int = Field(default=120, ge=1)

    # --- PostgreSQL (required when repository_backend = "postgres") ---
    # Full async DSN: postgresql+asyncpg://user:pass@host:5432/dbname
    # In AWS this is constructed at startup from Secrets Manager; never hardcode it here.
    database_url: str | None = None
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=5, ge=0, le=50)
    # CA bundle for verifying the server certificate (RDS: global-bundle.pem).
    # Leave unset for local Docker Postgres.
    db_ssl_root_cert: str | None = None

    # --- Google sign-in (accounts) ---
    # OAuth "Web application" client ID from Google Cloud Console. Not a secret, but unset
    # means Google sign-in is off and /v1/auth/google returns 503.
    google_client_id: str | None = None
    # Optional: only accept accounts from this Google Workspace domain (e.g. "example.com").
    google_hosted_domain: str | None = None
    account_token_ttl_hours: int = Field(default=168, ge=1, le=24 * 30)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1)
    # Log-in attempts per email address (any client), so one account can't be guessed at
    # from many IP addresses.
    login_attempts_per_email: int = Field(default=10, ge=1)
    login_attempt_window_minutes: int = Field(default=15, ge=1)

    # --- Password reset email ---
    # "none": reset is off (503). "outbox": local only, prints the email to the console.
    # "ses": Amazon SES; needs EMAIL_FROM (a verified SES identity) and APP_BASE_URL.
    email_provider: Literal["none", "outbox", "ses"] = "none"
    email_from: str | None = None
    ses_region: str = "us-east-2"
    # The front end's address; reset links point to {APP_BASE_URL}/reset-password.
    app_base_url: str | None = None
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    # Reset emails per address, and reset requests per client IP.
    reset_emails_per_hour: int = Field(default=3, ge=1)
    reset_requests_per_hour: int = Field(default=10, ge=1)
    # Callback requests ("talk to a licensed representative"): per IP and across everyone.
    support_rate_limit_per_hour: int = Field(default=5, ge=1)
    support_global_rate_limit_per_hour: int = Field(default=200, ge=1)
    # The original Planner session API (/v1/sessions...). The current front end doesn't use it,
    # and its unauthenticated POST /v1/sessions writes to the database, so it's off by default.
    planner_api_enabled: bool = False

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

    @field_validator("google_client_id", "google_hosted_domain", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("google_client_id")
    @classmethod
    def _client_id_shape(cls, value: str | None) -> str | None:
        if value is not None and not value.strip().endswith(".apps.googleusercontent.com"):
            raise ValueError(
                "GOOGLE_CLIENT_ID should look like <numbers>-<id>.apps.googleusercontent.com"
            )
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _provider_needs_key(self) -> Settings:
        key = self.anthropic_api_key.get_secret_value().strip() if self.anthropic_api_key else ""
        if self.ai_provider == "anthropic" and not key:
            raise ValueError("AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return self

    @field_validator("email_from", "app_base_url", mode="before")
    @classmethod
    def _blank_email_setting(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("app_base_url")
    @classmethod
    def _base_url_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not value.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            raise ValueError("APP_BASE_URL must be an https:// address (or localhost)")
        return value

    @model_validator(mode="after")
    def _email_settings(self) -> Settings:
        if self.email_provider == "outbox" and self.env not in ("local", "test", "dev"):
            raise ValueError("EMAIL_PROVIDER=outbox prints reset links; use it only locally")
        if self.email_provider != "none" and not self.app_base_url:
            raise ValueError("Password reset email needs APP_BASE_URL (the front end's address)")
        if self.email_provider == "ses" and not self.email_from:
            raise ValueError("EMAIL_PROVIDER=ses needs EMAIL_FROM (a verified SES identity)")
        return self

    @field_validator("db_ssl_root_cert")
    @classmethod
    def _cert_exists(cls, value: str | None) -> str | None:
        if value is not None and not Path(value).is_file():
            raise ValueError(f"DB_SSL_ROOT_CERT file not found: {value}")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
