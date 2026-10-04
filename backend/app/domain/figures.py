"""Check the dollar figures in a model's answer against the figures the code computed.

The model explains; it never decides a number. Every dollar amount in its answer must match an
amount the calculation produced for this person (or one they typed themselves), rounded the way
the model wrote it and within 5% ("$1.11M" matches 1,111,500; "$2 million" does not match
1,584,500). Anything else and the answer is not shown.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable

from app.domain.compass import (
    COLLEGE_COST,
    FINAL_EXPENSES,
    REPLACE,
    STEP,
    CompassProfile,
    compute,
)

# "$1,111,500", "$58.5k", "$1.11M", "$1.1 million", "$950K"
_AMOUNT_RE = re.compile(
    r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s?(k|m|b|thousand|million|billion)?\b",
    re.IGNORECASE,
)
_UNITS = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def amounts_in(text: str) -> list[tuple[str, float, float]]:
    """Every dollar amount in the text: (as written, value, precision of how it was written)."""
    found = []
    for match in _AMOUNT_RE.finditer(text):
        whole, decimals, unit = match.group(1), match.group(2) or "", (match.group(3) or "").lower()
        scale = _UNITS.get(unit, 1.0)
        value = float(f"{whole.replace(',', '')}.{decimals or 0}") * scale
        precision = scale / (10 ** len(decimals))
        found.append((match.group(0).strip(), value, precision))
    return found


def computed_amounts(p: CompassProfile) -> set[float]:
    """Every dollar amount the app itself shows or derives for this profile."""
    c = compute(p)
    values: set[float] = {
        p.income, p.mortgage, p.otherDebt, p.group, p.policies, p.savings, p.monthlyBudget,
        p.income * REPLACE, c.total, c.existing, c.gap, c.suggested, c.low, c.high,
        p.monthlyBudget * 12, p.monthlyBudget * 12 * c.term,
        float(FINAL_EXPENSES), float(STEP), *(float(v) for v in COLLEGE_COST.values()),
        p.income * 2,  # "2x salary" work coverage
    }  # fmt: skip
    values.update(line.amount for line in c.lines)
    # The alternatives the trade-off cards and the Breakdown compute.
    for variant in (
        p.model_copy(update={"group": 0}),
        p.model_copy(update={"college": "half"}),
        p.model_copy(update={"years": c.years + 1}),
        p.model_copy(update={"income": p.income + 10_000}),
    ):
        alt = compute(variant)
        values.update({alt.suggested, alt.total, abs(alt.suggested - c.suggested)})
    values.update(
        {
            math.ceil(p.mortgage / STEP) * STEP,
            math.ceil((c.lines[0].amount + c.lines[2].amount) / STEP) * STEP,
        }
    )
    return {round(v, 2) for v in values if v > 0}


def unverified(text: str, allowed: Iterable[float]) -> list[str]:
    """The dollar amounts in `text` that match none of `allowed`.

    A match is the computed amount rounded the way the model wrote it, and never more than 5%
    away, so "$1.43M" passes for $1,425,000 but "$2 million" doesn't pass for $1,584,500.
    """
    pool = list(allowed)
    return [
        written
        for written, value, precision in amounts_in(text)
        if not any(abs(value - a) <= min(precision / 2, a * 0.05) + 0.005 for a in pool)
    ]


def user_amounts(messages: Iterable[str]) -> set[float]:
    """Amounts the person typed themselves (a model may repeat them back)."""
    out: set[float] = set()
    for message in messages:
        out.update(value for _, value, _ in amounts_in(message))
        # Plain numbers people type without "$", like "I make 90000".
        out.update(
            float(n.replace(",", ""))
            for n in re.findall(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{4,}\b", message)
        )
    return out
