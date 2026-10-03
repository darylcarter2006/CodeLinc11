"""Template-based explanations built only from calculator output.

No model is involved: every number in the text comes from the breakdown.
"""

from __future__ import annotations

from app.domain.assessment import AssessmentBreakdown, AssessmentStatus, LineItemCode
from app.domain.profile import FIELD_SPECS


def format_usd(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,}"


def explain(breakdown: AssessmentBreakdown) -> str | None:
    if breakdown.status is AssessmentStatus.INCOMPLETE:
        labels = [FIELD_SPECS[name].label.lower() for name in breakdown.missing_fields]
        return "To estimate a coverage gap I still need: " + "; ".join(labels) + "."

    items = {item.code: item for item in breakdown.line_items}

    def amount(code: LineItemCode) -> str:
        return format_usd(abs(items[code].amount))

    shortfall = format_usd(breakdown.annual_shortfall or 0)
    text = (
        f"Annual shortfall of {shortfall} for {breakdown.support_years} years "
        f"({amount(LineItemCode.ONGOING_SUPPORT)}) plus one-time expenses of "
        f"{amount(LineItemCode.ONE_TIME_EXPENSES)}, minus assets applied "
        f"({amount(LineItemCode.AVAILABLE_ASSETS)}), personal coverage "
        f"({amount(LineItemCode.PERSONAL_COVERAGE)}) and employer coverage "
        f"({amount(LineItemCode.EMPLOYER_COVERAGE)}), leaves an additional coverage gap of "
        f"{amount(LineItemCode.ADDITIONAL_GAP)}."
    )
    if breakdown.status is AssessmentStatus.PARTIAL:
        text += " This is a partial estimate until the highlighted answers are confirmed."
    return text
