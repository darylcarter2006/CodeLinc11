"""Builds the service graph from settings. The only place concrete adapters are chosen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.base import AIAdapter
from app.ai.stub import StubAIAdapter
from app.repositories.base import SessionRepository
from app.repositories.memory import InMemorySessionRepository
from app.repositories.users import InMemoryUserRepository, UserRepository
from app.security.google import GoogleAuthVerifier, GoogleTokenVerifier
from app.security.rate_limit import RateLimiter
from app.services.accounts import AccountService
from app.services.assessments import AssessmentService
from app.services.compass_ai import CompassAIService
from app.services.conversation import ConversationService
from app.services.profiles import ProfileService
from app.services.sessions import Clock, SessionService
from app.settings import Settings


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Container:
    settings: Settings
    repo: SessionRepository
    ai: AIAdapter
    sessions: SessionService
    profiles: ProfileService
    conversation: ConversationService
    assessments: AssessmentService
    compass_ai: CompassAIService
    ai_limiter: RateLimiter
    accounts: AccountService
    auth_limiter: RateLimiter


def build_repository(settings: Settings) -> SessionRepository:
    if settings.repository_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("REPOSITORY_BACKEND=postgres requires DATABASE_URL to be set.")
        from app.db.session import build_engine
        from app.repositories.postgres import PostgresSessionRepository

        build_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            ssl_root_cert=settings.db_ssl_root_cert,
        )
        return PostgresSessionRepository(
            max_messages_per_session=settings.message_history_turns * 2
        )

    # Default: in-memory (no database required).
    return InMemorySessionRepository(max_messages_per_session=settings.message_history_turns * 2)


def build_user_repository(settings: Settings) -> UserRepository:
    if settings.repository_backend == "postgres":
        # Shares the engine created by build_repository.
        from app.repositories.postgres_users import PostgresUserRepository

        return PostgresUserRepository()
    return InMemoryUserRepository()


def build_google_verifier(settings: Settings) -> GoogleTokenVerifier | None:
    if settings.google_client_id is None:
        return None
    return GoogleAuthVerifier(settings.google_client_id, settings.google_hosted_domain)


def build_ai_adapter(settings: Settings) -> AIAdapter:
    if settings.ai_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("AI_PROVIDER=openai requires OPENAI_API_KEY to be set.")
        from app.ai.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model_fast=settings.openai_model_fast,
            model_smart=settings.openai_model_smart,
        )
    return StubAIAdapter()


def build_container(
    settings: Settings,
    *,
    repo: SessionRepository | None = None,
    ai: AIAdapter | None = None,
    users: UserRepository | None = None,
    google_verifier: GoogleTokenVerifier | None = None,
    clock: Clock = utc_now,
) -> Container:
    repo = repo or build_repository(settings)
    ai = ai or build_ai_adapter(settings)
    users = users or build_user_repository(settings)
    google_verifier = google_verifier or build_google_verifier(settings)
    return Container(
        settings=settings,
        repo=repo,
        ai=ai,
        sessions=SessionService(repo, settings, clock),
        profiles=ProfileService(repo, settings, clock),
        conversation=ConversationService(repo, ai, settings, clock),
        assessments=AssessmentService(repo, clock),
        compass_ai=CompassAIService(ai, settings.ai_timeout_seconds),
        ai_limiter=RateLimiter(settings.ai_rate_limit_per_minute),
        accounts=AccountService(users, google_verifier, settings.account_token_ttl_hours, clock),
        auth_limiter=RateLimiter(settings.auth_rate_limit_per_minute),
    )
