"""Question plan: the backend, not the model, decides what to ask next.

Questions are plain configuration. To add a topic, add a ``Question`` here; routing
logic does not change. The ``text`` is approved fallback copy, used whenever the AI
adapter is unavailable or its phrasing fails validation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from app.domain.profile import (
    CRITICAL_FIELDS,
    FIELD_SPECS,
    MAX_DEPENDENTS,
    MAX_MONEY,
    MAX_SUPPORT_YEARS,
    Profile,
)

InputType = Literal["integer", "currency", "expenses", "confirm"]

REVIEW_FIELD = "review"


@dataclass(frozen=True)
class Question:
    field: str
    text: str
    input_type: InputType
    min: int | None = None
    max: int | None = None
    allow_unknown: bool = True
    # Only set on the review question: fields the user should check or supply.
    review_fields: tuple[str, ...] = ()


QUESTIONS: tuple[Question, ...] = (
    Question(
        field="dependents_count",
        text="How many people depend on your financial support?",
        input_type="integer",
        min=0,
        max=MAX_DEPENDENTS,
    ),
    Question(
        field="annual_support_need",
        text=(
            "Roughly how much household spending per year would need to continue "
            "if you were no longer here?"
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="annual_survivor_contribution",
        text=(
            "Is there income that would continue toward those expenses, such as a "
            "spouse's earnings? If so, about how much per year?"
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="support_years",
        text="About how many years would you want that support to continue?",
        input_type="integer",
        min=1,
        max=MAX_SUPPORT_YEARS,
    ),
    Question(
        field="one_time_expenses",
        text=(
            "Are there one-time costs you want covered, such as final expenses, education, "
            "or paying off debt? Roughly what is the total?"
        ),
        input_type="expenses",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="personal_coverage",
        text=(
            "How much life insurance do you have on your own, outside of work? "
            "It's fine to say you don't know."
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="employer_coverage",
        text=(
            "How much life insurance do you have through an employer? "
            "It's fine to say you don't know."
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="available_assets",
        text=(
            "How much in savings or other assets would you want to count toward these needs? "
            "You can say none."
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
    Question(
        field="budget_monthly",
        text=(
            "Optional: is there a monthly amount you'd be comfortable spending on coverage? "
            "This is only noted for later and does not change the estimate."
        ),
        input_type="currency",
        min=0,
        max=MAX_MONEY,
    ),
)

REVIEW_QUESTION = Question(
    field=REVIEW_FIELD,
    text=(
        "Here's what I have so far. Please review these answers and confirm or correct "
        "them so the estimate uses values you agree with."
    ),
    input_type="confirm",
    allow_unknown=False,
)

QUESTIONS_BY_FIELD: dict[str, Question] = {question.field: question for question in QUESTIONS}

assert all(question.field in FIELD_SPECS for question in QUESTIONS)


def fields_needing_review(profile: Profile) -> list[str]:
    """Answered-but-unconfirmed fields, plus critical fields the user said were unknown."""
    fields = []
    for name in FIELD_SPECS:
        value = profile.field(name)
        if value is None:
            continue
        if not value.confirmed or (name in CRITICAL_FIELDS and value.value is None):
            fields.append(name)
    return fields


def next_question(profile: Profile) -> Question | None:
    for question in QUESTIONS:
        if profile.field(question.field) is None:
            return question
    review_fields = fields_needing_review(profile)
    if review_fields:
        return replace(REVIEW_QUESTION, review_fields=tuple(review_fields))
    return None
