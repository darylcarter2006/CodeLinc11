"""Builds the service graph from settings. The only place concrete adapters are chosen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.ai.base import AIAdapter
from app.ai.stub import StubAIAdapter
from app.repositories.base import SessionRepository
from app.repositories.memory import InMemorySessionRepository
from app.services.assessments import AssessmentService
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


def build_ai_adapter(settings: Settings) -> AIAdapter:
    # "bedrock" is added here in implementation step 5.
    return StubAIAdapter()


def build_container(
    settings: Settings,
    *,
    repo: SessionRepository | None = None,
    ai: AIAdapter | None = None,
    clock: Clock = utc_now,
) -> Container:
    repo = repo or build_repository(settings)
    ai = ai or build_ai_adapter(settings)
    return Container(
        settings=settings,
        repo=repo,
        ai=ai,
        sessions=SessionService(repo, settings, clock),
        profiles=ProfileService(repo, settings, clock),
        conversation=ConversationService(repo, ai, settings, clock),
        assessments=AssessmentService(repo, clock),
    )
