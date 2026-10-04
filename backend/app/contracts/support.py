"""Callback requests: "Talk to a licensed Lincoln Financial representative".

Shape matches ``frontend/src/services/support.ts`` and the contract in ``frontend/README.md``.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Never accept anything that looks like a Social Security number or an account number: the
# form only needs a name, one contact method, and what they want help with.
_SSN_RE = re.compile(r"\b\d{3}[-\s.]?\d{2}[-\s.]?\d{4}\b")
_LONG_NUMBER_RE = re.compile(r"\d(?:[\s-]?\d){9,}")  # 10+ digits: account or card numbers
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_CHARS_RE = re.compile(r"^[\d\s()+.-]+$")

Money = Field(ge=0, le=1_000_000_000)


def _no_sensitive_numbers(text: str) -> str:
    if _SSN_RE.search(text) or _LONG_NUMBER_RE.search(text):
        raise ValueError("Please don't include Social Security, account or card numbers.")
    return text


class EstimateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: float = Money
    existing: float = Money
    gap: float = Money
    suggested: float = Money
    termYears: int = Field(ge=0, le=60)


class CallbackSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estimate: EstimateSummary
    recentQuestions: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("recentQuestions")
    @classmethod
    def _questions(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(q.split())[:500] for q in value if q.strip()]
        for question in cleaned:
            _no_sensitive_numbers(question)
        return cleaned


class CallbackRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    contactMethod: Literal["email", "phone"]
    contact: str = Field(min_length=3, max_length=254)
    bestTime: Literal["any", "morning", "afternoon", "evening"]
    topic: str = Field(min_length=1, max_length=1000)
    summary: CallbackSummary | None = None

    @field_validator("name", "topic")
    @classmethod
    def _text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return _no_sensitive_numbers(value)

    @model_validator(mode="after")
    def _contact_matches_method(self) -> CallbackRequestIn:
        contact = self.contact.strip()
        if self.contactMethod == "email":
            if not _EMAIL_RE.match(contact):
                raise ValueError("contact must be an email address")
            contact = contact.lower()
        else:
            digits = re.sub(r"\D", "", contact)
            if not _PHONE_CHARS_RE.match(contact) or not 10 <= len(digits) <= 15:
                raise ValueError("contact must be a phone number with area code")
        self.contact = contact
        return self


class CallbackRequestOut(BaseModel):
    id: str
