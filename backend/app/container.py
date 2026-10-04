"""Builds the service graph from settings. The only place concrete adapters are chosen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.base import AIAdapter
from app.ai.stub import StubAIAdapter
from app.notifications.email import EmailSender, OutboxEmailSender
from app.repositories.base import SessionRepository
from app.repositories.callbacks import CallbackRepository, InMemoryCallbackRepository
from app.repositories.memory import InMemorySessionRepository
from app.repositories.profile_states import (
    InMemoryProfileStateRepository,
    ProfileStateRepository,
)
from app.repositories.users import InMemoryUserRepository, UserRepository
from app.security.google import GoogleAuthVerifier, GoogleTokenVerifier
from app.security.rate_limit import RateLimiter
from app.services.accounts import AccountService
from app.services.assessments import AssessmentService
from app.services.compass_ai import CompassAIService
from app.services.conversation import ConversationService
from app.services.personal_data import PersonalDataService
from app.services.profiles import ProfileService
from app.services.sessions import Clock, SessionService
from app.services.support import SupportService
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
    ai_global_limiter: RateLimiter
    accounts: AccountService
    support: SupportService
    support_limiter: RateLimiter
    support_global_limiter: RateLimiter
    auth_limiter: RateLimiter
    reset_ip_limiter: RateLimiter
    profile_states: ProfileStateRepository
    email: EmailSender
    clock: Clock
    personal_data: PersonalDataService


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


def build_callback_repository(settings: Settings) -> CallbackRepository:
    if settings.repository_backend == "postgres":
        from app.repositories.postgres_callbacks import PostgresCallbackRepository

        return PostgresCallbackRepository()
    return InMemoryCallbackRepository()


def build_profile_state_repository(settings: Settings) -> ProfileStateRepository:
    if settings.repository_backend == "postgres":
        from app.repositories.postgres_profile_states import PostgresProfileStateRepository

        return PostgresProfileStateRepository()
    return InMemoryProfileStateRepository()


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_provider == "ses":
        from app.notifications.email import SesEmailSender

        assert settings.email_from is not None  # checked by Settings
        return SesEmailSender(settings.email_from, settings.ses_region)
    # "outbox" keeps (and prints) messages; with "none", reset is off and nothing is sent.
    return OutboxEmailSender()


def build_google_verifier(settings: Settings) -> GoogleTokenVerifier | None:
    if settings.google_client_id is None:
        return None
    return GoogleAuthVerifier(settings.google_client_id, settings.google_hosted_domain)


def build_ai_adapter(settings: Settings) -> AIAdapter:
    if settings.ai_provider == "anthropic":
        from app.ai.claude import ClaudeAdapter

        return ClaudeAdapter(settings)
    return StubAIAdapter()


def build_container(
    settings: Settings,
    *,
    repo: SessionRepository | None = None,
    ai: AIAdapter | None = None,
    users: UserRepository | None = None,
    callbacks: CallbackRepository | None = None,
    profile_states: ProfileStateRepository | None = None,
    email: EmailSender | None = None,
    google_verifier: GoogleTokenVerifier | None = None,
    clock: Clock = utc_now,
) -> Container:
    repo = repo or build_repository(settings)
    ai = ai or build_ai_adapter(settings)
    users = users or build_user_repository(settings)
    callbacks = callbacks or build_callback_repository(settings)
    profile_states = profile_states or build_profile_state_repository(settings)
    email = email or build_email_sender(settings)
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
        ai_global_limiter=RateLimiter(settings.ai_global_rate_limit_per_minute),
        accounts=AccountService(
            users,
            google_verifier,
            settings.account_token_ttl_hours,
            clock,
            login_limiter=RateLimiter(
                settings.login_attempts_per_email,
                window_seconds=settings.login_attempt_window_minutes * 60,
            ),
            reset_limiter=RateLimiter(settings.reset_emails_per_hour, window_seconds=3600),
            reset_base_url=settings.app_base_url if settings.email_provider != "none" else None,
            reset_ttl_minutes=settings.password_reset_ttl_minutes,
        ),
        auth_limiter=RateLimiter(settings.auth_rate_limit_per_minute),
        reset_ip_limiter=RateLimiter(settings.reset_requests_per_hour, window_seconds=3600),
        profile_states=profile_states,
        email=email,
        clock=clock,
        personal_data=PersonalDataService(
            users,
            callbacks,
            clock,
            account_retention_days=settings.account_retention_days,
            callback_retention_days=settings.callback_retention_days,
        ),
        support=SupportService(callbacks, clock),
        support_limiter=RateLimiter(settings.support_rate_limit_per_hour, window_seconds=3600),
        support_global_limiter=RateLimiter(
            settings.support_global_rate_limit_per_hour, window_seconds=3600
        ),
    )
