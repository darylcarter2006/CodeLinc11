"""AI adapter interface.

The model may only *propose* candidate profile values, *phrase* questions, and
*compose* the final assistant reply. It never calculates; all numbers come from the
backend calculator, and everything the model returns is validated before use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from app.domain.questions import Question


class CandidateUpdate(BaseModel):
    """One proposed profile value. ``extra='forbid'`` rejects invented keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str = Field(max_length=64)
    # For "expenses" fields this is the total amount.
    value: int | None = None
    # The user said they don't know; ``value`` must then be None.
    unknown: bool = False
    # Verbatim span from the user's latest message that supports the value.
    evidence: str = Field(min_length=1, max_length=200)
    ambiguous: bool = False
    # The user is explicitly correcting an earlier answer.
    is_correction: bool = False


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[CandidateUpdate] = Field(default_factory=list, max_length=10)


@dataclass(frozen=True)
class ExtractionContext:
    message: str
    pending_field: str | None
    # Only the fields the model needs: name -> current value (no provenance, no IDs).
    known_values: dict[str, object] = field(default_factory=dict)
    # Bounded recent window, oldest first: (role, text).
    recent_messages: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResponseContext:
    """All backend-computed facts the model needs to write the assistant reply.

    The model MUST NOT invent numbers — every figure it uses must come from these fields.
    """

    # What the backend decided to say (acknowledgement + fallback question text).
    backend_text: str
    # The next question field name and approved question text (None when conversation done).
    next_field: str | None
    next_question_text: str | None
    # Structured calculation result for the current profile (None = incomplete).
    calculation_summary: str | None
    # Whether any fields were just updated this turn.
    fields_updated: list[str]
    # Whether clarification was needed on any fields.
    fields_to_clarify: list[str]
    # Recent conversation window, oldest first.
    recent_messages: tuple[tuple[str, str], ...] = ()


class AIAdapter(ABC):
    model_id: str

    @abstractmethod
    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult: ...

    @abstractmethod
    async def phrase_question(self, question: Question, context: ExtractionContext) -> str | None:
        """Optional friendlier wording. Return None to use the approved copy."""

    @abstractmethod
    async def generate_response(self, context: ResponseContext) -> str | None:
        """Write the full assistant reply given backend-computed facts.

        The model must not introduce new numbers; it only weaves together the facts
        in ``context``. Return None to fall back to ``context.backend_text``.
        """
