"""AI adapter interface.

The model may only *propose* candidate profile values and *phrase* questions. It never
calculates, and everything it returns is validated as untrusted input before use.
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


class AIAdapter(ABC):
    model_id: str

    @abstractmethod
    async def extract_candidates(self, context: ExtractionContext) -> ExtractionResult: ...

    @abstractmethod
    async def phrase_question(self, question: Question, context: ExtractionContext) -> str | None:
        """Optional friendlier wording. Return None to use the approved copy."""
