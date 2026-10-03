"""Typed request bodies for /v1. Unknown keys are rejected everywhere."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.profile import Age, Count, Money, OneTimeExpense, Years

ClientRequestId = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Revision = Annotated[int, Field(strict=True, ge=0)]

ConfirmableField = Literal[
    "dependents_count",
    "youngest_dependent_age",
    "annual_support_need",
    "annual_survivor_contribution",
    "support_years",
    "one_time_expenses",
    "available_assets",
    "personal_coverage",
    "employer_coverage",
    "budget_monthly",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionRequest(_Strict):
    pass


class MessageRequest(_Strict):
    # The configured MESSAGE_MAX_CHARS limit is enforced in the service; this is a hard cap.
    text: str = Field(min_length=1, max_length=10_000)
    client_request_id: ClientRequestId
    expected_revision: Revision


class AssumptionFlagsUpdate(_Strict):
    mortgage_payment_in_annual_support: bool | None = None
    education_in_annual_support: bool | None = None


class ProfileUpdates(_Strict):
    """Direct user edits. Include a key to set it; send ``null`` for "I don't know".

    Omitted keys are left unchanged. Values set here are recorded as
    ``source: "edited"`` and ``confirmed: true``.
    """

    dependents_count: Count | None = None
    youngest_dependent_age: Age | None = None
    annual_support_need: Money | None = None
    annual_survivor_contribution: Money | None = None
    support_years: Years | None = None
    one_time_expenses: list[OneTimeExpense] | None = None
    available_assets: Money | None = None
    personal_coverage: Money | None = None
    employer_coverage: Money | None = None
    budget_monthly: Money | None = None
    assumption_flags: AssumptionFlagsUpdate | None = None


class ProfilePatchRequest(_Strict):
    expected_revision: Revision
    client_request_id: ClientRequestId
    updates: ProfileUpdates = Field(default_factory=ProfileUpdates)
    # Accept existing values as correct without changing them.
    confirm: list[ConfirmableField] = Field(default_factory=list, max_length=20)


class CreateAssessmentRequest(_Strict):
    # Optional guard: refuse to save if the profile changed since the client last saw it.
    expected_revision: Revision | None = None


class ScenarioOverrides(_Strict):
    annual_support_need: Money | None = None
    annual_survivor_contribution: Money | None = None
    support_years: Years | None = None
    available_assets: Money | None = None
    personal_coverage: Money | None = None
    employer_coverage: Money | None = None
    exclude_employer_coverage: bool = False


class ScenarioSpec(_Strict):
    name: str = Field(min_length=1, max_length=40)
    overrides: ScenarioOverrides


class ScenarioRequest(_Strict):
    base_revision: Revision
    scenarios: list[ScenarioSpec] = Field(min_length=1, max_length=5)
