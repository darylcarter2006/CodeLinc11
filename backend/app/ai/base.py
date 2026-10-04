"""AI adapter interface.

The model may only *propose* candidate profile values, *phrase* questions, and *explain*
results. It never calculates, and everything it returns is validated as untrusted input
before use.

Two layers:
* ``extract_candidates`` / ``phrase_question`` serve the session API's question flow.
* ``generate`` / ``stream`` are plain text-in, text-out calls used by the Coverage Compass
  endpoints. Prompts and validation live in ``app.services.compass_ai``; a provider only
  moves text. Providers without a model keep the defaults, which raise ModelUnavailable.
The model may only *propose* candidate profile values, *phrase* questions, and
*compose* the final assistant reply. It never calculates; all numbers come from the
backend calculator, and everything the model returns is validated before use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.questions import Question


class ModelUnavailable(Exception):
    """No model is configured, or the provider cannot be reached."""


class ModelThrottled(Exception):
    """The provider is rate limiting us."""


class ModelFailed(Exception):
    """The provider returned an error for this request."""


# "fast": a low-cost model for short structured tasks; "smart": a stronger model for chat.
ModelTier = Literal["fast", "smart"]


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


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

    async def generate(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> str:
        """Return one complete reply. Raises ModelUnavailable/ModelThrottled/ModelFailed."""
        raise ModelUnavailable()

    def stream(
        self, system: str, messages: list[ChatMessage], *, tier: ModelTier, max_tokens: int
    ) -> AsyncIterator[str]:
        """Yield the reply in chunks. Raises the same errors as ``generate``."""
        raise ModelUnavailable()

    @abstractmethod
    async def generate_response(self, context: ResponseContext) -> str | None:
        """Write the full assistant reply given backend-computed facts.

        The model must not introduce new numbers; it only weaves together the facts
        in ``context``. Return None to fall back to ``context.backend_text``.
        """
