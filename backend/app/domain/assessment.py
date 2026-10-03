"""Calculator output types. Pure data; no framework imports."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class AssessmentStatus(StrEnum):
    # A critical input is missing or unknown; no numbers are produced.
    INCOMPLETE = "incomplete"
    # Numbers are produced, but some inputs are unconfirmed or were treated as $0.
    PARTIAL = "partial"
    # Every input used is known and confirmed by the user.
    COMPLETE = "complete"


class LineItemCode(StrEnum):
    ONGOING_SUPPORT = "ongoing_support"
    ONE_TIME_EXPENSES = "one_time_expenses"
    AVAILABLE_ASSETS = "available_assets"
    PERSONAL_COVERAGE = "personal_coverage"
    EMPLOYER_COVERAGE = "employer_coverage"
    ADDITIONAL_GAP = "additional_gap"


class LineItem(BaseModel):
    """One row of the breakdown.

    ``amount`` is the signed amount actually used, so rows 1-5 always sum to row 6.
    For offsets, ``entered_amount`` is what the user entered; it differs from
    ``-amount`` only when the offset exceeds the remaining need.
    """

    model_config = ConfigDict(frozen=True)

    code: LineItemCode
    label: str
    amount: int
    entered_amount: int | None = None
    display_order: int


class AssessmentBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    calculation_version: str
    status: AssessmentStatus
    currency: str = "USD"
    missing_fields: list[str]
    # Used in the numbers but unknown (treated as $0), unanswered, or not yet confirmed.
    unresolved_fields: list[str]
    annual_shortfall: int | None
    support_years: int | None
    line_items: list[LineItem]
    additional_coverage_gap: int | None
    # Internal analysis value; may be negative. Never shown to users as the gap.
    raw_gap: int | None
    assumptions: list[str]
    warnings: list[str]
