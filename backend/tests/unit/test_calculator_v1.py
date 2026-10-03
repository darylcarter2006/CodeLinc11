from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.calculators import v1
from app.calculators.registry import CURRENT_VERSION, get_policy
from app.domain.assessment import AssessmentStatus, LineItemCode
from app.domain.profile import CALCULATION_FIELDS, Source
from tests.factories import EXAMPLE_VALUES, make_profile

FIXTURES = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "needs_v1_cases.json").read_text()
)
calculate = get_policy("needs-v1").calculate


def _amounts(breakdown: Any) -> dict[str, int]:
    return {item.code.value: item.amount for item in breakdown.line_items}


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_golden_cases(case: dict[str, Any]) -> None:
    assert FIXTURES["calculation_version"] == CURRENT_VERSION
    result = calculate(make_profile(**case["inputs"]))
    expected = case["expected"]

    assert result.annual_shortfall == expected["annual_shortfall"]
    assert result.raw_gap == expected["raw_gap"]
    assert result.additional_coverage_gap == expected["additional_coverage_gap"]
    assert _amounts(result) == expected["line_items"]


@pytest.mark.parametrize("case", FIXTURES["cases"], ids=lambda c: c["name"])
def test_line_items_always_sum_to_gap(case: dict[str, Any]) -> None:
    result = calculate(make_profile(**case["inputs"]))
    rows = sorted(result.line_items, key=lambda item: item.display_order)
    assert [item.display_order for item in rows] == [1, 2, 3, 4, 5, 6]
    assert sum(item.amount for item in rows[:-1]) == rows[-1].amount


def test_blueprint_example_is_complete_when_all_confirmed() -> None:
    result = calculate(make_profile(**EXAMPLE_VALUES))
    assert result.status is AssessmentStatus.COMPLETE
    assert result.additional_coverage_gap == 670_000
    assert result.unresolved_fields == []
    assert result.calculation_version == "needs-v1"


def test_offsets_report_entered_and_applied_amounts() -> None:
    result = calculate(make_profile(**FIXTURES["cases"][1]["inputs"]))
    personal = next(i for i in result.line_items if i.code is LineItemCode.PERSONAL_COVERAGE)
    assert personal.entered_amount == 100_000
    assert personal.amount == -40_000


@pytest.mark.parametrize(
    "missing", ["annual_support_need", "annual_survivor_contribution", "support_years"]
)
def test_missing_critical_field_produces_no_numbers(missing: str) -> None:
    values = {k: v for k, v in EXAMPLE_VALUES.items() if k != missing}
    result = calculate(make_profile(**values))
    assert result.status is AssessmentStatus.INCOMPLETE
    assert result.missing_fields == [missing]
    assert result.additional_coverage_gap is None
    assert result.line_items == []


def test_unknown_critical_field_is_incomplete_not_zero() -> None:
    result = calculate(make_profile(**{**EXAMPLE_VALUES, "annual_survivor_contribution": None}))
    assert result.status is AssessmentStatus.INCOMPLETE
    assert result.missing_fields == ["annual_survivor_contribution"]


def test_unconfirmed_values_give_partial_result() -> None:
    result = calculate(make_profile(confirmed=False, source=Source.STATED, **EXAMPLE_VALUES))
    assert result.status is AssessmentStatus.PARTIAL
    assert result.additional_coverage_gap == 670_000
    assert set(result.unresolved_fields) == set(CALCULATION_FIELDS)
    assert "Support for 15 years (not yet confirmed)" in result.assumptions


def test_unknown_offsets_are_treated_as_zero_and_labeled() -> None:
    values = {**EXAMPLE_VALUES, "personal_coverage": None}
    values.pop("employer_coverage")
    result = calculate(make_profile(**values))

    assert result.status is AssessmentStatus.PARTIAL
    assert result.additional_coverage_gap == 920_000
    assert {"personal_coverage", "employer_coverage"} <= set(result.unresolved_fields)
    assert "Personal life insurance: unknown, treated as $0." in result.assumptions
    assert "Employer life insurance: not answered yet, treated as $0." in result.assumptions


def test_user_entered_zeros_are_valid_and_complete() -> None:
    values = {
        **EXAMPLE_VALUES,
        "one_time_expenses": [],
        "available_assets": 0,
        "personal_coverage": 0,
        "employer_coverage": 0,
    }
    result = calculate(make_profile(**values))
    assert result.status is AssessmentStatus.COMPLETE
    assert result.additional_coverage_gap == 900_000
    assert v1.EMPLOYER_COVERAGE_WARNING not in result.warnings


def test_zero_gap_warns_it_is_not_a_guarantee() -> None:
    result = calculate(make_profile(**FIXTURES["cases"][1]["inputs"]))
    assert v1.ZERO_GAP_WARNING in result.warnings


def test_employer_coverage_warning() -> None:
    result = calculate(make_profile(**EXAMPLE_VALUES))
    assert v1.EMPLOYER_COVERAGE_WARNING in result.warnings


def _with_expense(category: str, **flags: bool | None) -> dict[str, Any]:
    return {
        **EXAMPLE_VALUES,
        "one_time_expenses": [{"id": "x", "label": "X", "category": category, "amount": 1000}],
        "assumption_flags": flags,
    }


@pytest.mark.parametrize(
    ("category", "flags", "expected"),
    [
        (
            "mortgage_payoff",
            {"mortgage_payment_in_annual_support": True},
            v1.MORTGAGE_DOUBLE_COUNT_WARNING,
        ),
        ("mortgage_payoff", {}, v1.MORTGAGE_UNCLEAR_WARNING),
        ("education", {"education_in_annual_support": True}, v1.EDUCATION_DOUBLE_COUNT_WARNING),
        ("education", {}, v1.EDUCATION_UNCLEAR_WARNING),
    ],
)
def test_double_count_warnings(category: str, flags: dict[str, bool], expected: str) -> None:
    result = calculate(make_profile(**_with_expense(category, **flags)))
    assert expected in result.warnings


def test_corrected_mortgage_assumption_clears_warning() -> None:
    values = _with_expense("mortgage_payoff", mortgage_payment_in_annual_support=False)
    result = calculate(make_profile(**values))
    assert v1.MORTGAGE_DOUBLE_COUNT_WARNING not in result.warnings
    assert v1.MORTGAGE_UNCLEAR_WARNING not in result.warnings


def test_calculation_is_deterministic_and_does_not_mutate_input() -> None:
    profile = make_profile(**EXAMPLE_VALUES)
    snapshot = profile.model_dump()
    assert calculate(profile) == calculate(profile)
    assert profile.model_dump() == snapshot


def test_unknown_policy_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown calculation version"):
        get_policy("needs-v0")
