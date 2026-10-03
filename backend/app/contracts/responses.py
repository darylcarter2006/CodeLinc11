"""Typed response bodies for /v1. These shapes are the contract with the frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.domain.assessment import AssessmentStatus, LineItemCode
from app.domain.profile import Profile


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    current_revision: int | None = None
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class NextQuestion(BaseModel):
    field: str
    text: str
    input_type: Literal["integer", "currency", "expenses", "confirm"]
    min: int | None
    max: int | None
    allow_unknown: bool
    # Only for input_type "confirm": the fields to show for review.
    review_fields: list[str]


class LineItemOut(BaseModel):
    code: LineItemCode
    label: str
    amount: int
    entered_amount: int | None
    display_order: int


class AssessmentPreview(BaseModel):
    """A live calculation against the current profile. Not saved."""

    status: AssessmentStatus
    calculation_version: str
    currency: str
    missing_fields: list[str]
    unresolved_fields: list[str]
    annual_shortfall: int | None
    support_years: int | None
    line_items: list[LineItemOut]
    additional_coverage_gap: int | None
    assumptions: list[str]
    warnings: list[str]
    explanation: str | None
    disclaimer: str
    limitations: list[str]


class AssessmentResponse(AssessmentPreview):
    """A saved, immutable assessment."""

    id: str
    profile_revision: int
    is_current: bool
    stale_reason: str | None
    created_at: datetime


class SessionCreatedResponse(BaseModel):
    session_id: str
    revision: int
    access_token: str
    expires_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    expires_at: datetime


class ProfileResponse(BaseModel):
    session_id: str
    revision: int
    profile: Profile
    next_question: NextQuestion | None
    assessment: AssessmentPreview


class SessionResponse(ProfileResponse):
    turn_count: int
    turn_limit: int
    expires_at: datetime


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class MessagesResponse(BaseModel):
    session_id: str
    messages: list[MessageOut]


class MessageResponse(ProfileResponse):
    assistant_message: str
    warnings: list[str]


class ScenarioResult(BaseModel):
    name: str
    overrides: dict[str, Any]
    result: AssessmentPreview


class GapRange(BaseModel):
    """Min/max gap across the base and named scenarios. Not a probability range."""

    low: int
    high: int


class ScenarioResponse(BaseModel):
    base_revision: int
    base: AssessmentPreview
    scenarios: list[ScenarioResult]
    range: GapRange | None


class CoverageTypeOut(BaseModel):
    id: str
    title: str
    summary: str
    points: list[str]


class ResourceOut(BaseModel):
    title: str
    summary: str
    url: str
    source_owner: str


class CoverageTypesResponse(BaseModel):
    content_version: str
    review_status: str
    coverage_types: list[CoverageTypeOut]
    resources: list[ResourceOut]
    disclaimer: str


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
