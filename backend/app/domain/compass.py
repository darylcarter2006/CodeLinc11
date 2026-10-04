"""Coverage Compass profile, field validation and needs calculation.

Ported from the front end (``frontend/src/domain/profile.ts``, ``parse.ts`` and
``needs.ts``) so the server can validate model output and ground chat answers in numbers
it computed itself, instead of trusting figures sent by the browser. Keep the two in step:
the handoff's test vectors run against both.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Dep = Literal["partner", "kids", "relative", "none"]
College = Literal["public", "half", "none"]
CoverFor = Literal["period", "lifelong"]
Budget = Literal["lowest", "more"]
YesNo = Literal["yes", "no"]

DEPS: tuple[str, ...] = ("partner", "kids", "relative", "none")
COLLEGES: tuple[str, ...] = ("public", "half", "none")
MONEY_FIELDS: tuple[str, ...] = (
    "income", "mortgage", "otherDebt", "group", "policies", "savings", "monthlyBudget",
)  # fmt: skip
INT_FIELDS: tuple[str, ...] = ("children", "youngest", "years", "mortgageYears")
# Coverage-type preferences and the values each may take (front end: domain/profile.ts).
POLICY_CHOICES: dict[str, tuple[str, ...]] = {
    "coverFor": ("period", "lifelong"),
    "budget": ("lowest", "more"),
    "cashValue": ("no", "yes"),
    "legacy": ("no", "yes"),
    "simple": ("yes", "no"),
}
# Which side each answer adds a point to (front end: domain/policy.ts).
POLICY_SIDE: dict[str, dict[str, str]] = {
    "coverFor": {"period": "term", "lifelong": "perm"},
    "budget": {"lowest": "term", "more": "perm"},
    "cashValue": {"no": "term", "yes": "perm"},
    "legacy": {"no": "term", "yes": "perm"},
    "simple": {"yes": "term", "no": "perm"},
}
POLICY_REASON: dict[str, dict[str, str]] = {
    "coverFor": {
        "period": "wants coverage for a specific period",
        "lifelong": "wants lifelong coverage",
    },
    "budget": {
        "lowest": "wants the lowest monthly cost",
        "more": "is willing to pay more for added benefits",
    },
    "cashValue": {"no": "doesn't need cash value", "yes": "wants cash value to use while alive"},
    "legacy": {
        "no": "isn't aiming to leave extra to heirs",
        "yes": "wants to leave money to heirs",
    },
    "simple": {
        "yes": "prefers a simple policy that just pays out",
        "no": "wants extra options like cash value or flexible payments",
    },
}

# Every profile field, in the front end's order.
FIELDS: tuple[str, ...] = (
    "deps", "children", "youngest", "income", "years", "mortgage",
    "mortgageYears", "otherDebt", "college", "group", "policies", "savings", "monthlyBudget",
    *POLICY_CHOICES,
)  # fmt: skip
MAX_INT = 120
MAX_MONEY = 1_000_000_000

REPLACE = 0.75
FINAL_EXPENSES = 15_000
COLLEGE_COST = {"public": 100_000, "half": 50_000, "none": 0}
STEP = 25_000
TERMS = (10, 15, 20, 25, 30)
# Income support lasts at least until the youngest child reaches this age.
ADULT_AGE = 18

Money = Annotated[float, Field(ge=0, le=MAX_MONEY)]
Small = Annotated[int, Field(ge=0, le=MAX_INT)]


class CompassProfile(BaseModel):
    """The profile as the front end sends it. Unknown keys are ignored, not trusted."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    deps: list[Dep] = Field(default_factory=list, max_length=4)
    children: Small = 0
    youngest: Small = 0
    income: Money = 0
    years: Small = 0
    mortgage: Money = 0
    mortgageYears: Small = 0
    otherDebt: Money = 0
    college: College = "none"
    group: Money = 0
    policies: Money = 0
    savings: Money = 0
    # What they could comfortably spend on coverage each month; 0 means not sure.
    monthlyBudget: Money = 0
    # Coverage-type preferences; None means not answered (the browser omits those).
    coverFor: CoverFor | None = None
    budget: Budget | None = None
    cashValue: YesNo | None = None
    legacy: YesNo | None = None
    simple: YesNo | None = None

    def has(self, dep: str) -> bool:
        return dep in self.deps


def clean(updates: object) -> dict[str, Any]:
    """Keep only valid profile values; mirrors ``clean()`` in ``frontend/src/domain/parse.ts``.

    * ``deps``: kept if at least one entry is allowed; collapses to ``["none"]`` if present.
    * ``college``: kept only if it is a known value.
    * numbers: finite and >= 0, rounded; counts and ages capped at 120. Money is capped
      at $1B so an absurd value cannot reach the calculation.
    * anything else is dropped.
    """
    out: dict[str, Any] = {}
    if not isinstance(updates, dict):
        return out
    for key, value in updates.items():
        if key == "deps" and isinstance(value, list):
            deps = [d for d in value if isinstance(d, str) and d in DEPS]
            if deps:
                out["deps"] = ["none"] if "none" in deps else list(dict.fromkeys(deps))
        elif key == "college" and isinstance(value, str) and value in COLLEGES:
            out["college"] = value
        elif key in POLICY_CHOICES and isinstance(value, str) and value in POLICY_CHOICES[key]:
            out[key] = value
        elif key in MONEY_FIELDS or key in INT_FIELDS:
            number = _as_number(value)
            if number is None or number < 0:
                continue
            if key in INT_FIELDS:
                out[key] = min(MAX_INT, _round_half_up(number))
            else:
                out[key] = min(MAX_MONEY, _round_half_up(number))
    return out


def _as_number(value: object) -> float | None:
    # Same coercion as JavaScript's unary plus for the inputs a model realistically sends:
    # numbers and numeric strings. Booleans, null and empty strings are rejected.
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str) and value.strip():
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _round_half_up(number: float) -> int:
    # JavaScript's Math.round rounds .5 up; Python's round() rounds half to even.
    return math.floor(number + 0.5)


@dataclass(frozen=True)
class Line:
    key: str
    label: str
    amount: float
    how: str


@dataclass(frozen=True)
class Calculation:
    lines: tuple[Line, ...]
    total: float
    existing: float
    gap: float
    suggested: int
    low: int
    high: int
    years: int
    kids: int
    term: int


def _usd(amount: float) -> str:
    return f"${round(amount):,}"


def compute(p: CompassProfile) -> Calculation:
    """Needs calculation; mirrors ``compute()`` in ``frontend/src/domain/needs.ts``."""
    kids = p.children if p.has("kids") else 0
    years_entered = 0 if p.has("none") else p.years
    until_adult = max(0, ADULT_AGE - p.youngest) if kids > 0 else 0
    years = max(years_entered, until_adult)
    extended = (
        f" (until your youngest turns {ADULT_AGE}; you entered {years_entered})"
        if years > years_entered
        else ""
    )
    per_child = COLLEGE_COST[p.college]
    lines = (
        Line(
            "c1",
            "Income replacement",
            p.income * REPLACE * years,
            f"75% of {_usd(p.income)} × {years} years{extended}"
            if years
            else "No one relies on your income, so none is needed",
        ),
        Line(
            "c2",
            "Debts to clear",
            p.mortgage + p.otherDebt,
            f"{_usd(p.mortgage)} mortgage + {_usd(p.otherDebt)} other debts",
        ),
        Line(
            "c3",
            "College",
            kids * per_child,
            f"{kids} {'children' if kids > 1 else 'child'} × {_usd(per_child)}"
            if kids
            else "No children included",
        ),
        Line("c4", "Final expenses", FINAL_EXPENSES, "Typical funeral and settling costs"),
    )
    total = sum(line.amount for line in lines)
    existing = p.group + p.policies + p.savings
    gap = max(0.0, total - existing)
    term_need = max(years, p.mortgageYears if p.mortgage > 0 else 0)
    term = next((t for t in TERMS if t >= term_need), 30)
    return Calculation(
        lines=lines,
        total=total,
        existing=existing,
        gap=gap,
        suggested=math.ceil(gap / STEP) * STEP,
        low=math.floor(gap * 0.85 / STEP) * STEP,
        high=math.ceil(gap * 1.15 / STEP) * STEP,
        years=years,
        kids=kids,
        term=term,
    )


@dataclass(frozen=True)
class PolicyFit:
    type: Literal["term", "perm"]
    term: int
    perm: int
    reasons: tuple[str, ...]


def policy_fit(p: CompassProfile) -> PolicyFit | None:
    """Hidden tally over the five preferences: higher score wins, a tie goes to term.

    Returns None until every preference is answered. Mirrors ``policyFit()`` in
    ``frontend/src/domain/policy.ts``.
    """
    answers = [getattr(p, field) for field in POLICY_CHOICES]
    if any(answer is None for answer in answers):
        return None
    sides = [
        POLICY_SIDE[field][answer] for field, answer in zip(POLICY_CHOICES, answers, strict=True)
    ]
    term = sides.count("term")
    perm = sides.count("perm")
    reasons = tuple(
        POLICY_REASON[field][answer] for field, answer in zip(POLICY_CHOICES, answers, strict=True)
    )
    return PolicyFit(type="perm" if perm > term else "term", term=term, perm=perm, reasons=reasons)
