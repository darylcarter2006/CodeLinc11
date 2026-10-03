from __future__ import annotations

import asyncio

import pytest

from app.ai.base import ExtractionContext, ExtractionResult
from app.ai.stub import StubAIAdapter


def extract(text: str, field: str | None = "annual_support_need") -> ExtractionResult:
    context = ExtractionContext(message=text, pending_field=field)
    return asyncio.run(StubAIAdapter().extract_candidates(context))


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("We spend about $80,000 a year", 80_000),
        ("80k", 80_000),
        ("roughly 1.5 million", 1_500_000),
        ("$1,250,000", 1_250_000),
        ("75000", 75_000),
    ],
)
def test_reads_dollar_amounts(text: str, value: int) -> None:
    [candidate] = extract(text).candidates
    assert candidate.value == value
    assert not candidate.ambiguous
    assert candidate.evidence in text


@pytest.mark.parametrize(("text", "value"), [("two kids", 2), ("3", 3), ("no one", 0)])
def test_reads_counts(text: str, value: int) -> None:
    [candidate] = extract(text, "dependents_count").candidates
    assert candidate.value == value


@pytest.mark.parametrize("text", ["I don't know", "not sure", "skip"])
def test_unknown_answers(text: str) -> None:
    [candidate] = extract(text).candidates
    assert candidate.unknown is True
    assert candidate.value is None


@pytest.mark.parametrize("text", ["none", "nothing", "zero"])
def test_none_answers_are_zero(text: str) -> None:
    [candidate] = extract(text).candidates
    assert candidate.value == 0


@pytest.mark.parametrize(
    "text",
    [
        "We spend $80,000 and my spouse earns $20,000",  # two different amounts
        "about 70%",  # a percentage is not a dollar amount
        "$80,000.50",  # cents
    ],
)
def test_ambiguous_answers_ask_for_clarification(text: str) -> None:
    [candidate] = extract(text).candidates
    assert candidate.ambiguous is True


def test_no_pending_question_extracts_nothing() -> None:
    assert extract("80k", field=None).candidates == []


def test_unrelated_text_extracts_nothing() -> None:
    assert extract("hello there").candidates == []


def test_phrasing_defers_to_approved_copy() -> None:
    from app.domain.questions import QUESTIONS

    context = ExtractionContext(message="", pending_field=None)
    assert asyncio.run(StubAIAdapter().phrase_question(QUESTIONS[0], context)) is None
