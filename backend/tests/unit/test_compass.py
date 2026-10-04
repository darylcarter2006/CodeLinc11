"""The Python port must match frontend/src/domain/needs.ts and parse.ts exactly."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.compass import CompassProfile, clean, compute

MAYA = CompassProfile(
    deps=["partner", "kids"], children=2, youngest=3, age=34, income=78_000, years=19,
    mortgage=240_000, mortgageYears=26, otherDebt=18_000, college="public",
    group=156_000, policies=0, savings=20_000,
)  # fmt: skip


# The three test vectors from docs/coverage-compass/HANDOFF.md.
def test_maya_example() -> None:
    c = compute(MAYA)
    assert (c.total, c.existing, c.gap) == (1_584_500, 176_000, 1_408_500)
    assert (c.suggested, c.low, c.high, c.term) == (1_425_000, 1_175_000, 1_625_000, 30)


def test_half_college() -> None:
    p = CompassProfile(
        deps=["partner", "kids"], children=2, youngest=4, income=85_000, years=18,
        mortgage=210_000, mortgageYears=22, otherDebt=12_000, college="half",
        group=170_000, savings=15_000,
    )  # fmt: skip
    c = compute(p)
    assert (c.total, c.existing, c.gap, c.suggested, c.term) == (
        1_484_500, 185_000, 1_299_500, 1_300_000, 25,
    )  # fmt: skip


def test_already_covered() -> None:
    p = CompassProfile(deps=["none"], income=60_000, otherDebt=20_000, group=50_000)
    c = compute(p)
    assert (c.total, c.existing, c.gap, c.suggested, c.term) == (35_000, 50_000, 0, 0, 10)


def test_exact_multiple_is_not_rounded_up() -> None:
    p = CompassProfile(deps=["none"], otherDebt=35_000)  # total 50,000
    assert compute(p).suggested == 50_000


def test_one_dollar_over_rounds_up() -> None:
    p = CompassProfile(deps=["none"], otherDebt=35_001)
    assert compute(p).suggested == 75_000


def test_years_and_children_ignored_when_they_do_not_apply() -> None:
    p = CompassProfile(deps=["none"], children=3, years=20, income=100_000, college="public")
    c = compute(p)
    assert c.lines[0].amount == 0
    assert c.lines[2].amount == 0


def test_term_caps_at_thirty_and_uses_mortgage_years_only_with_a_mortgage() -> None:
    assert compute(CompassProfile(deps=["partner"], years=40)).term == 30
    assert compute(CompassProfile(deps=["partner"], years=5, mortgageYears=25)).term == 10
    with_mortgage = CompassProfile(deps=["partner"], years=5, mortgage=1, mortgageYears=25)
    assert compute(with_mortgage).term == 25


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"income": 85000}, {"income": 85000}),
        ({"income": "85000"}, {"income": 85000}),  # numeric strings, like JS unary plus
        ({"income": 2.5}, {"income": 3}),  # Math.round rounds .5 up
        ({"age": 130}, {"age": 120}),  # ages and counts capped at 120
        ({"savings": -1}, {}),
        ({"savings": True}, {}),
        ({"savings": None}, {}),
        ({"savings": ""}, {}),
        ({"savings": "85k"}, {}),
        ({"savings": float("inf")}, {}),
        ({"deps": ["partner", "kids"]}, {"deps": ["partner", "kids"]}),
        ({"deps": ["kids", "none"]}, {"deps": ["none"]}),
        ({"deps": ["robot"]}, {}),
        ({"college": "half"}, {"college": "half"}),
        ({"college": "ivy"}, {}),
        ({"gap": 0, "recommended": 1}, {}),  # unknown keys dropped
        ({"income": 1e15}, {"income": 1_000_000_000}),
    ],
)
def test_clean(updates: dict[str, Any], expected: dict[str, Any]) -> None:
    assert clean(updates) == expected


@pytest.mark.parametrize("bad", [None, [], "income: 5", 42])
def test_clean_rejects_non_objects(bad: Any) -> None:
    assert clean(bad) == {}


def test_years_reach_the_youngest_childs_18th_birthday() -> None:
    family = CompassProfile(
        deps=["partner", "kids"], children=2, youngest=2, years=15, income=78_000
    )
    calc = compute(family)
    assert calc.years == 16
    assert calc.lines[0].amount == 78_000 * 0.75 * 16
    assert (
        calc.lines[0].how
        == "75% of $78,000 × 16 years (until your youngest turns 18; you entered 15)"  # noqa: RUF001 (the app uses a real multiplication sign)
    )
    grown = CompassProfile(deps=["kids"], children=1, youngest=20, years=15, income=78_000)
    assert compute(grown).years == 15
    no_kids = CompassProfile(deps=["partner"], youngest=2, years=15, income=78_000)
    assert compute(no_kids).years == 15


# --- coverage type (mirrors frontend/src/domain/policy.ts) -----------------------------

from app.domain.compass import policy_fit  # noqa: E402

TERM_ANSWERS = {
    "coverFor": "period",
    "budget": "lowest",
    "cashValue": "no",
    "legacy": "no",
    "simple": "yes",
}


def test_policy_fit_needs_every_answer() -> None:
    assert policy_fit(CompassProfile()) is None
    partial = {k: v for k, v in TERM_ANSWERS.items() if k != "simple"}
    assert policy_fit(CompassProfile(**partial)) is None


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, ("term", 5, 0)),
        (
            {
                "coverFor": "lifelong",
                "budget": "more",
                "cashValue": "yes",
                "legacy": "yes",
                "simple": "no",
            },
            ("perm", 0, 5),
        ),
        ({"coverFor": "lifelong", "cashValue": "yes", "legacy": "yes"}, ("perm", 2, 3)),
        ({"coverFor": "lifelong", "cashValue": "yes"}, ("term", 3, 2)),
    ],
)
def test_policy_fit_tally(changes: dict[str, str], expected: tuple[str, int, int]) -> None:
    fit = policy_fit(CompassProfile(**{**TERM_ANSWERS, **changes}))
    assert fit is not None
    assert (fit.type, fit.term, fit.perm) == expected
    assert len(fit.reasons) == 5


def test_clean_accepts_only_known_policy_choices() -> None:
    assert clean({"coverFor": "lifelong", "budget": "free", "cashValue": True, "simple": "no"}) == {
        "coverFor": "lifelong",
        "simple": "no",
    }
