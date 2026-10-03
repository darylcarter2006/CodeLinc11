"""needs-v1: nominal-dollar coverage-gap model.

    annual_shortfall = max(0, annual_support_need - annual_survivor_contribution)
    need_total       = annual_shortfall * support_years + sum(one_time_expenses)

Offsets are then applied in a fixed order (assets, personal coverage, employer
coverage), each capped at the need still remaining, so the line items always sum to
the displayed gap. ``raw_gap`` subtracts the full offsets and may be negative.
"""

from __future__ import annotations

from app.calculators.base import CalculationPolicy
from app.domain.assessment import AssessmentBreakdown, AssessmentStatus, LineItem, LineItemCode
from app.domain.profile import (
    CALCULATION_FIELDS,
    CRITICAL_FIELDS,
    FIELD_SPECS,
    ExpenseCategory,
    OneTimeExpense,
    Profile,
)

VERSION = "needs-v1"

NOMINAL_DOLLARS = "Nominal dollars; inflation and investment returns are not modeled."
EMPLOYER_COVERAGE_WARNING = (
    "Employer coverage may change or end with employment and is not guaranteed to be portable."
)
ZERO_GAP_WARNING = (
    "Under these inputs there is no additional gap. That is not a guarantee that "
    "current coverage is sufficient."
)
MORTGAGE_DOUBLE_COUNT_WARNING = (
    "Your annual spending includes mortgage payments and you also added a mortgage payoff. "
    "That may count the mortgage twice; remove one or lower your annual spending."
)
MORTGAGE_UNCLEAR_WARNING = (
    "You added a mortgage payoff. Please confirm whether your annual spending also includes "
    "mortgage payments, so the mortgage is not counted twice."
)
EDUCATION_DOUBLE_COUNT_WARNING = (
    "Your annual spending includes education costs and you also added a one-time education "
    "amount. That may count education twice; remove one or lower your annual spending."
)
EDUCATION_UNCLEAR_WARNING = (
    "You added a one-time education amount. Please confirm whether your annual spending "
    "also includes education costs, so it is not counted twice."
)


def _known_int(profile: Profile, name: str) -> int:
    field = profile.field(name)
    if field is None or field.value is None:
        return 0
    value: int = field.value
    return value


def _expenses(profile: Profile) -> list[OneTimeExpense]:
    field = profile.one_time_expenses
    if field is None or field.value is None:
        return []
    return list(field.value)


def _missing_fields(profile: Profile) -> list[str]:
    missing = []
    for name in CRITICAL_FIELDS:
        field = profile.field(name)
        if field is None or field.value is None:
            missing.append(name)
    return missing


def _unresolved_fields(profile: Profile) -> list[str]:
    unresolved = []
    for name in CALCULATION_FIELDS:
        field = profile.field(name)
        if field is None or field.value is None or not field.confirmed:
            unresolved.append(name)
    return unresolved


def _double_count_warnings(profile: Profile) -> list[str]:
    warnings = []
    categories = {expense.category for expense in _expenses(profile)}
    flags = profile.assumption_flags
    if ExpenseCategory.MORTGAGE_PAYOFF in categories:
        if flags.mortgage_payment_in_annual_support is True:
            warnings.append(MORTGAGE_DOUBLE_COUNT_WARNING)
        elif flags.mortgage_payment_in_annual_support is None:
            warnings.append(MORTGAGE_UNCLEAR_WARNING)
    if ExpenseCategory.EDUCATION in categories:
        if flags.education_in_annual_support is True:
            warnings.append(EDUCATION_DOUBLE_COUNT_WARNING)
        elif flags.education_in_annual_support is None:
            warnings.append(EDUCATION_UNCLEAR_WARNING)
    return warnings


def _assumptions(profile: Profile, support_years: int) -> list[str]:
    assumptions = []
    years_field = profile.support_years
    years_note = "" if years_field is not None and years_field.confirmed else " (not yet confirmed)"
    assumptions.append(f"Support for {support_years} years{years_note}")
    assumptions.append(NOMINAL_DOLLARS)
    assumptions.append("Only the assets you chose to count are applied.")
    for name in CALCULATION_FIELDS:
        if name in CRITICAL_FIELDS:
            continue
        field = profile.field(name)
        label = FIELD_SPECS[name].label
        if field is None:
            assumptions.append(f"{label}: not answered yet, treated as $0.")
        elif field.value is None:
            assumptions.append(f"{label}: unknown, treated as $0.")
    return assumptions


class NeedsV1(CalculationPolicy):
    version = VERSION

    def calculate(self, profile: Profile) -> AssessmentBreakdown:
        warnings = _double_count_warnings(profile)
        missing = _missing_fields(profile)
        if missing:
            return AssessmentBreakdown(
                calculation_version=self.version,
                status=AssessmentStatus.INCOMPLETE,
                missing_fields=missing,
                unresolved_fields=_unresolved_fields(profile),
                annual_shortfall=None,
                support_years=None,
                line_items=[],
                additional_coverage_gap=None,
                raw_gap=None,
                assumptions=[],
                warnings=warnings,
            )

        support_need = _known_int(profile, "annual_support_need")
        contribution = _known_int(profile, "annual_survivor_contribution")
        support_years = _known_int(profile, "support_years")
        assets = _known_int(profile, "available_assets")
        personal = _known_int(profile, "personal_coverage")
        employer = _known_int(profile, "employer_coverage")

        annual_shortfall = max(0, support_need - contribution)
        ongoing_total = annual_shortfall * support_years
        one_time_total = sum(expense.amount for expense in _expenses(profile))
        remaining = ongoing_total + one_time_total

        assets_applied = min(assets, remaining)
        remaining -= assets_applied
        personal_applied = min(personal, remaining)
        remaining -= personal_applied
        employer_applied = min(employer, remaining)
        remaining -= employer_applied

        gap = remaining
        raw_gap = ongoing_total + one_time_total - assets - personal - employer

        if employer > 0:
            warnings.append(EMPLOYER_COVERAGE_WARNING)
        if gap == 0:
            warnings.append(ZERO_GAP_WARNING)

        unresolved = _unresolved_fields(profile)
        line_items = [
            LineItem(
                code=LineItemCode.ONGOING_SUPPORT,
                label="Ongoing support",
                amount=ongoing_total,
                display_order=1,
            ),
            LineItem(
                code=LineItemCode.ONE_TIME_EXPENSES,
                label="One-time expenses",
                amount=one_time_total,
                display_order=2,
            ),
            LineItem(
                code=LineItemCode.AVAILABLE_ASSETS,
                label="Assets applied",
                amount=-assets_applied,
                entered_amount=assets,
                display_order=3,
            ),
            LineItem(
                code=LineItemCode.PERSONAL_COVERAGE,
                label="Personal coverage",
                amount=-personal_applied,
                entered_amount=personal,
                display_order=4,
            ),
            LineItem(
                code=LineItemCode.EMPLOYER_COVERAGE,
                label="Employer coverage",
                amount=-employer_applied,
                entered_amount=employer,
                display_order=5,
            ),
            LineItem(
                code=LineItemCode.ADDITIONAL_GAP,
                label="Additional coverage gap",
                amount=gap,
                display_order=6,
            ),
        ]
        return AssessmentBreakdown(
            calculation_version=self.version,
            status=AssessmentStatus.PARTIAL if unresolved else AssessmentStatus.COMPLETE,
            missing_fields=[],
            unresolved_fields=unresolved,
            annual_shortfall=annual_shortfall,
            support_years=support_years,
            line_items=line_items,
            additional_coverage_gap=gap,
            raw_gap=raw_gap,
            assumptions=_assumptions(profile, support_years),
            warnings=warnings,
        )
