"""Coverage Compass AI endpoint contracts. Shapes match "Backend AI contract" in
``frontend/README.md``, including its camelCase field names."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.compass import CompassProfile

# Total characters across the chat history sent in one request (about 3,000 tokens).
MAX_HISTORY_CHARS = 12_000

AskedField = Literal[
    "deps", "children", "youngest", "age", "income", "years", "mortgage",
    "mortgageYears", "otherDebt", "college", "group", "policies", "savings",
]  # fmt: skip


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    askedField: AskedField
    question: str = Field(max_length=500)
    profile: CompassProfile
    # The front end trims to 500; anything longer is rejected rather than silently cut.
    message: str = Field(min_length=1, max_length=500)


class ExtractResponse(BaseModel):
    # Only valid profile values (see app.domain.compass.clean); possibly empty.
    updates: dict[str, Any]
    ack: str
    answer: str


class ChatTurnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    # Real turns are short (chat answers are under ~120 words); this also limits how much a
    # client can stuff into fabricated history.
    content: str = Field(max_length=2000)


class ChatContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    profile: CompassProfile
    # Sent by the front end but not trusted: the server recomputes it from the profile.
    calculation: dict[str, Any] | None = None
    firstName: str | None = Field(default=None, max_length=60)
    example: bool = False


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatTurnIn] = Field(min_length=1, max_length=16)
    context: ChatContext

    @model_validator(mode="after")
    def _bounded_history(self) -> ChatRequest:
        if sum(len(m.content) for m in self.messages) > MAX_HISTORY_CHARS:
            raise ValueError(f"conversation is limited to {MAX_HISTORY_CHARS} characters")
        return self
