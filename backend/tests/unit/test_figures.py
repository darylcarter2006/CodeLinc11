"""The check that keeps model-written dollar figures in line with the calculation."""

from __future__ import annotations

import pytest

from app.domain.compass import CompassProfile
from app.domain.figures import amounts_in, computed_amounts, unverified, user_amounts

MAYA = CompassProfile(
    deps=["partner", "kids"], children=2, youngest=3, income=78_000, years=19,
    mortgage=240_000, mortgageYears=26, otherDebt=18_000, college="public",
    group=156_000, policies=0, savings=20_000, monthlyBudget=60,
)  # fmt: skip
# Maya: income 75% x 19 = $1,111,500; debts $258,000; college $200,000; final $15,000;
# total $1,584,500; in place $176,000; left $1,408,500; starting point $1,425,000.


def test_amounts_are_read_with_the_precision_they_were_written() -> None:
    assert amounts_in("about $1.11M, or $58.5k, $950K and $1,425,000") == [
        ("$1.11M", 1_110_000, 10_000),
        ("$58.5k", 58_500, 100),
        ("$950K", 950_000, 1_000),
        ("$1,425,000", 1_425_000, 1),
    ]
    assert amounts_in("$1.4 million") == [("$1.4 million", 1_400_000, 100_000)]
    assert amounts_in("no money here, 75% and 19 years") == []


@pytest.mark.parametrize(
    "text",
    [
        "75% of $78,000 is $58,500, times 19 years is $1,111,500.",
        "Your starting point is $1,425,000 (about $1.43M), within $1,175,000 to $1.63M.",
        "About $1.4M is left to cover after the $176,000 you have.",
        "Your $60 a month is $720 a year.",
        "Leaving out work coverage raises it to $1,575,000.",
    ],
)
def test_figures_from_the_calculation_pass(text: str) -> None:
    assert unverified(text, computed_amounts(MAYA)) == []


@pytest.mark.parametrize(
    ("text", "bad"),
    [
        ("You need about $2 million.", ["$2 million"]),
        ("Your starting point is $1,500,000.", ["$1,500,000"]),
        ("A policy like this costs around $45 a month.", ["$45"]),
        ("The range runs to $1.65M.", ["$1.65M"]),  # the top is $1,625,000
        ("Left to cover: $1.2M.", []),  # the low end ($1,175,000) written to one decimal
    ],
)
def test_figures_the_code_never_produced_are_caught(text: str, bad: list[str]) -> None:
    assert unverified(text, computed_amounts(MAYA)) == bad


def test_amounts_the_person_typed_may_be_repeated() -> None:
    typed = user_amounts(["What if I earned $90,000?", "or 95000 a year"])
    assert typed == {90_000, 95_000}
    assert unverified("At $90,000 the income line changes; update My info to see it.", typed) == []
