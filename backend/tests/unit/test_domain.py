from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.profile import Profile
from app.domain.questions import QUESTIONS, REVIEW_FIELD, next_question
from app.security.tokens import generate_token, hash_token
from tests.factories import EXAMPLE_PATCH, make_profile


@pytest.mark.parametrize("bad", [80_000.5, 80_000.0, -1, True, "80000", 10**10])
def test_money_rejects_non_integer_dollars(bad: Any) -> None:
    with pytest.raises(ValidationError):
        Profile.model_validate({"annual_support_need": {"value": bad, "source": "edited"}})


def test_unknown_is_distinct_from_zero() -> None:
    unknown = make_profile(personal_coverage=None)
    zero = make_profile(personal_coverage=0)
    assert unknown.personal_coverage is not None
    assert unknown.personal_coverage.value is None
    assert zero.personal_coverage is not None
    assert zero.personal_coverage.value == 0


def test_duplicate_expense_categories_rejected() -> None:
    item = {"label": "Education", "category": "education", "amount": 1}
    with pytest.raises(ValidationError):
        make_profile(one_time_expenses=[{**item, "id": "a"}, {**item, "id": "b"}])


def test_profile_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Profile.model_validate({"favorite_color": {"value": 1, "source": "edited"}})


def test_questions_follow_configured_order() -> None:
    profile = Profile()
    asked = []
    for _ in QUESTIONS:
        question = next_question(profile)
        assert question is not None
        asked.append(question.field)
        profile = profile.with_fields(
            {question.field: {"value": None, "source": "stated", "confirmed": False}}
        )
    assert asked == [q.field for q in QUESTIONS]


def test_review_question_lists_unconfirmed_fields() -> None:
    profile = make_profile(confirmed=False, **EXAMPLE_PATCH)
    question = next_question(profile)
    assert question is not None
    assert question.field == REVIEW_FIELD
    assert question.input_type == "confirm"
    assert "support_years" in question.review_fields


def test_no_question_when_everything_is_confirmed() -> None:
    assert next_question(make_profile(**EXAMPLE_PATCH)) is None


def test_review_keeps_asking_for_unknown_critical_fields() -> None:
    profile = make_profile(**{**EXAMPLE_PATCH, "support_years": None})
    question = next_question(profile)
    assert question is not None
    assert question.review_fields == ("support_years",)


def test_tokens_are_random_and_hashed() -> None:
    first, second = generate_token(), generate_token()
    assert first != second
    assert len(first) == 64
    assert hash_token(first) != first
    assert hash_token(first) == hash_token(first)
