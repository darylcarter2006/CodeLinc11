"""Household profile: typed fields, each carrying provenance metadata.

Conventions
-----------
* A profile field that is ``None`` has not been answered yet.
* A ``ProfileValue`` whose ``value`` is ``None`` means the user said "I don't know".
  Unknown is never the same as zero.
* Money is nonnegative integer USD dollars. Decimals are rejected, not rounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_MONEY = 1_000_000_000
MAX_SUPPORT_YEARS = 60
MAX_DEPENDENTS = 20
MAX_AGE = 120

Money = Annotated[int, Field(strict=True, ge=0, le=MAX_MONEY)]
Count = Annotated[int, Field(strict=True, ge=0, le=MAX_DEPENDENTS)]
Age = Annotated[int, Field(strict=True, ge=0, le=MAX_AGE)]
Years = Annotated[int, Field(strict=True, ge=0, le=MAX_SUPPORT_YEARS)]


class Source(StrEnum):
    STATED = "stated"  # extracted from something the user said
    EDITED = "edited"  # entered or corrected directly by the user
    ASSUMPTION = "assumption"  # a default or derived value the user has not supplied


class ProfileValue[T](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: T | None
    source: Source
    confirmed: bool = False


class ExpenseCategory(StrEnum):
    FINAL_EXPENSES = "final_expenses"
    EDUCATION = "education"
    DEBT_PAYOFF = "debt_payoff"
    MORTGAGE_PAYOFF = "mortgage_payoff"
    OTHER = "other"


class OneTimeExpense(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    category: ExpenseCategory
    amount: Money


def _no_duplicate_categories(items: list[OneTimeExpense]) -> list[OneTimeExpense]:
    categories = [item.category for item in items]
    if len(categories) != len(set(categories)):
        raise ValueError("one_time_expenses may contain each category at most once")
    return items


OneTimeExpenses = Annotated[list[OneTimeExpense], Field(max_length=len(ExpenseCategory))]


class AssumptionFlags(BaseModel):
    """Answers that decide how to avoid double counting. ``None`` means not asked yet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mortgage_payment_in_annual_support: bool | None = None
    education_in_annual_support: bool | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dependents_count: ProfileValue[Count] | None = None
    youngest_dependent_age: ProfileValue[Age] | None = None
    annual_support_need: ProfileValue[Money] | None = None
    annual_survivor_contribution: ProfileValue[Money] | None = None
    support_years: ProfileValue[Years] | None = None
    one_time_expenses: ProfileValue[OneTimeExpenses] | None = None
    available_assets: ProfileValue[Money] | None = None
    personal_coverage: ProfileValue[Money] | None = None
    employer_coverage: ProfileValue[Money] | None = None
    budget_monthly: ProfileValue[Money] | None = None
    assumption_flags: AssumptionFlags = AssumptionFlags()

    @field_validator("one_time_expenses")
    @classmethod
    def _check_expenses(
        cls, value: ProfileValue[list[OneTimeExpense]] | None
    ) -> ProfileValue[list[OneTimeExpense]] | None:
        if value is not None and value.value is not None:
            _no_duplicate_categories(value.value)
        return value

    def field(self, name: str) -> ProfileValue[Any] | None:
        result: ProfileValue[Any] | None = getattr(self, name)
        return result

    def with_fields(self, updates: dict[str, Any]) -> Profile:
        """Return a new, re-validated profile with the given fields replaced."""
        data = self.model_dump(mode="python")
        for name, value in updates.items():
            data[name] = value.model_dump(mode="python") if isinstance(value, BaseModel) else value
        return Profile.model_validate(data)


FieldKind = Literal["money", "count", "years", "age", "expenses"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: FieldKind
    min: int = 0
    max: int = MAX_MONEY


# Every profile field the conversation or a PATCH may set. Nothing outside this map
# can ever be written to a profile.
FIELD_SPECS: dict[str, FieldSpec] = {
    spec.name: spec
    for spec in [
        FieldSpec("dependents_count", "Number of dependents", "count", max=MAX_DEPENDENTS),
        FieldSpec("youngest_dependent_age", "Youngest dependent's age", "age", max=MAX_AGE),
        FieldSpec("annual_support_need", "Annual household spending to support", "money"),
        FieldSpec("annual_survivor_contribution", "Continuing annual income", "money"),
        FieldSpec("support_years", "Years of support", "years", max=MAX_SUPPORT_YEARS),
        FieldSpec("one_time_expenses", "One-time expenses", "expenses"),
        FieldSpec("available_assets", "Assets you chose to count", "money"),
        FieldSpec("personal_coverage", "Personal life insurance", "money"),
        FieldSpec("employer_coverage", "Employer life insurance", "money"),
        FieldSpec("budget_monthly", "Monthly budget for coverage", "money"),
    ]
}

# Without these the calculator will not produce any number.
CRITICAL_FIELDS: tuple[str, ...] = (
    "annual_support_need",
    "annual_survivor_contribution",
    "support_years",
)

# Used by the calculator. If unanswered or unknown they are treated as $0, and the
# result is labeled "partial" until the user confirms a real value (which may be 0).
OFFSET_AND_EXPENSE_FIELDS: tuple[str, ...] = (
    "one_time_expenses",
    "available_assets",
    "personal_coverage",
    "employer_coverage",
)

CALCULATION_FIELDS: tuple[str, ...] = CRITICAL_FIELDS + OFFSET_AND_EXPENSE_FIELDS
