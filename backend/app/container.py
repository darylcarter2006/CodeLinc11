"""Builds the service graph from settings. The only place concrete adapters are chosen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

UTC = timezone.utc

from app.ai.base import AIAdapter
from app.ai.bedrock import BedrockAIAdapter
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
    # "postgres" is added here in implementation step 4 (see docs/blueprint.md §13).
    return InMemorySessionRepository(max_messages_per_session=settings.message_history_turns * 2)


def build_ai_adapter(settings: Settings) -> AIAdapter:
    if settings.ai_provider == "bedrock":
        return BedrockAIAdapter(
            model_id=settings.bedrock_model_id,
            region=settings.bedrock_region,
            guardrail_id=settings.bedrock_guardrail_id,
            guardrail_version=settings.bedrock_guardrail_version,
        )
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
