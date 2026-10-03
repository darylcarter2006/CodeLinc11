"""Validate untrusted candidate updates from the AI adapter.

Rules enforced in code (never only in the prompt):
* only known profile fields; anything else is dropped
* values must be in range for the field; percentages are never dollar amounts
* the evidence must appear verbatim in the user's latest message
* ambiguous or conflicting values become clarification questions, not overwrites
* extracted values are recorded as ``stated`` and **unconfirmed**
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.ai.base import CandidateUpdate, ExtractionResult
from app.domain.profile import (
    FIELD_SPECS,
    ExpenseCategory,
    OneTimeExpense,
    Profile,
    ProfileValue,
    Source,
)
from app.domain.questions import QUESTIONS_BY_FIELD

EXPENSE_TOTAL_ID = "one-time-total"
EXPENSE_TOTAL_LABEL = "One-time expenses (total)"

_PERCENT_RE = re.compile(r"%|\bpercent\b", re.IGNORECASE)
_SPACES_RE = re.compile(r"\s+")


@dataclass
class ExtractionOutcome:
    updates: dict[str, ProfileValue[Any]] = field(default_factory=dict)
    clarify: list[str] = field(default_factory=list)
    rejected: int = 0


def _normalize(text: str) -> str:
    return _SPACES_RE.sub(" ", text).strip().casefold()


def _bounds(name: str) -> tuple[int, int]:
    spec = FIELD_SPECS[name]
    question = QUESTIONS_BY_FIELD.get(name)
    low = question.min if question is not None and question.min is not None else spec.min
    return low, spec.max


def _to_profile_value(candidate: CandidateUpdate) -> ProfileValue[Any]:
    if candidate.unknown:
        return ProfileValue[Any](value=None, source=Source.STATED, confirmed=False)
    value: Any = candidate.value
    if FIELD_SPECS[candidate.field].kind == "expenses":
        value = (
            []
            if candidate.value == 0
            else [
                OneTimeExpense(
                    id=EXPENSE_TOTAL_ID,
                    label=EXPENSE_TOTAL_LABEL,
                    category=ExpenseCategory.OTHER,
                    amount=candidate.value or 0,
                )
            ]
        )
    return ProfileValue[Any](value=value, source=Source.STATED, confirmed=False)


def _is_valid(candidate: CandidateUpdate, message: str) -> bool:
    name = candidate.field
    if name not in FIELD_SPECS:
        return False
    if _normalize(candidate.evidence) not in _normalize(message):
        return False
    if candidate.unknown:
        return candidate.value is None
    if candidate.value is None:
        return False
    if FIELD_SPECS[name].kind == "money" and _PERCENT_RE.search(candidate.evidence):
        return False
    low, high = _bounds(name)
    return low <= candidate.value <= high


def validate_candidates(
    result: ExtractionResult, message: str, profile: Profile
) -> ExtractionOutcome:
    outcome = ExtractionOutcome()
    proposed: dict[str, ProfileValue[Any]] = {}
    corrections: set[str] = set()

    for candidate in result.candidates:
        if candidate.field not in FIELD_SPECS:
            outcome.rejected += 1
            continue
        if candidate.ambiguous:
            if candidate.field not in outcome.clarify:
                outcome.clarify.append(candidate.field)
            continue
        if not _is_valid(candidate, message):
            outcome.rejected += 1
            if candidate.field not in outcome.clarify:
                outcome.clarify.append(candidate.field)
            continue
        value = _to_profile_value(candidate)
        previous = proposed.get(candidate.field)
        if previous is not None and previous.value != value.value:
            # Two different values for one field in a single message.
            if candidate.field not in outcome.clarify:
                outcome.clarify.append(candidate.field)
            continue
        proposed[candidate.field] = value
        if candidate.is_correction:
            corrections.add(candidate.field)

    for name, value in proposed.items():
        if name in outcome.clarify:
            continue
        existing = profile.field(name)
        conflicts = existing is not None and existing.confirmed and existing.value != value.value
        if conflicts and name not in corrections:
            outcome.clarify.append(name)
            continue
        outcome.updates[name] = value
    return outcome
