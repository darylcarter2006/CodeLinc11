"""Stored entities. Repositories persist these; they hold no behavior."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.domain.assessment import AssessmentBreakdown
from app.domain.profile import Profile

SCHEMA_VERSION = "v1"


class ConversationState(BaseModel):
    model_config = ConfigDict(frozen=True)

    # The field the last assistant message asked about; gives extraction its context.
    pending_field: str | None = None


class SessionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    revision: int
    turn_count: int
    status: Literal["active"] = "active"
    schema_version: str = SCHEMA_VERSION
    profile: Profile
    conversation_state: ConversationState
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class MessageRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    turn_id: str
    created_at: datetime


class AssessmentRecord(BaseModel):
    """Immutable once saved. Staleness is derived at read time, never written back."""

    model_config = ConfigDict(frozen=True)

    id: str
    session_id: str
    profile_revision: int
    profile_snapshot: Profile
    result: AssessmentBreakdown
    created_at: datetime


class TokenRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_hash: str
    session_id: str
    expires_at: datetime
    created_at: datetime


class IdempotencyRecord(BaseModel):
    """Keyed by (session_id, client_request_id); replays return the stored response."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    client_request_id: str
    request_hash: str
    status_code: int
    response: dict[str, Any]
    created_at: datetime
    expires_at: datetime
