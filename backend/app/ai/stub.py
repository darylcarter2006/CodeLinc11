"""Deterministic rule-based adapter for local development, CI, and AI-free demos.

It only answers the question that was just asked (``pending_field``): it reads one
amount, an "I don't know", or a "none". Anything else becomes a clarification.
``generate_response`` always returns None so the backend-composed text is used.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.ai.base import AIAdapter, CandidateUpdate, ExtractionContext, ExtractionResult, ResponseContext
from app.domain.profile import FIELD_SPECS
from app.domain.questions import Question

_UNKNOWN_RE = re.compile(
    r"\b(don'?t know|do not know|not sure|unsure|no idea|unknown|skip)\b", re.IGNORECASE
)
_NONE_RE = re.compile(r"\b(none|nothing|nobody|no one|zero|nope|no)\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(
    r"\$?\s*(?P<number>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<fraction>\d+))?"
    r"\s*(?P<unit>k|thousand|mm|m|million|mil)?\b"
    r"(?P<percent>\s*(?:%|percent))?",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "thirty": 30,
}  # fmt: skip
# The lookbehind keeps "no one" from reading as the number 1.
_NUMBER_WORD_RE = re.compile(r"(?<!no )\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)
_MULTIPLIERS = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "mm": 1_000_000,
                "million": 1_000_000, "mil": 1_000_000}  # fmt: skip


def _amounts(text: str) -> list[tuple[int | None, str]]:
    """All numbers in the text as (integer value or None if not a whole amount, span)."""
    found: list[tuple[int | None, str]] = []
    for match in _AMOUNT_RE.finditer(text):
        span = match.group(0).strip()
        if match.group("percent"):
            found.append((None, span))  # a percentage is not a dollar amount
            continue
        raw = match.group("number").replace(",", "")
        if match.group("fraction"):
            raw += "." + match.group("fraction")
        try:
            number = Decimal(raw)
        except InvalidOperation:  # pragma: no cover - the regex only admits digits
            continue
        unit = (match.group("unit") or "").lower()
        number *= _MULTIPLIERS.get(unit, 1)
        found.append((int(number) if number == number.to_integral_value() else None, span))
    for match in _NUMBER_WORD_RE.finditer(text):
        found.append((_NUMBER_WORDS[match.group(1).lower()], match.group(0)))
    return found


class StubAIAdapter(AIAdapter):
    model_id = "stub-v1"

    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult:
        field = context.pending_field
        if field is None or field not in FIELD_SPECS:
            return ExtractionResult()
        text = context.message

        amounts = _amounts(text)
        distinct = {value for value, _ in amounts}
        if len(distinct) > 1 or (amounts and None in distinct):
            return ExtractionResult(
                candidates=[CandidateUpdate(field=field, evidence=amounts[0][1], ambiguous=True)]
            )
        if amounts:
            value, span = amounts[0]
            return ExtractionResult(
                candidates=[CandidateUpdate(field=field, value=value, evidence=span)]
            )

        unknown = _UNKNOWN_RE.search(text)
        if unknown:
            return ExtractionResult(
                candidates=[CandidateUpdate(field=field, unknown=True, evidence=unknown.group(0))]
            )
        none = _NONE_RE.search(text)
        if none:
            return ExtractionResult(
                candidates=[CandidateUpdate(field=field, value=0, evidence=none.group(0))]
            )
        return ExtractionResult()

    async def phrase_question(self, question: Question, context: ExtractionContext) -> str | None:
        return None

    async def generate_response(self, context: ResponseContext) -> str | None:
        return None
