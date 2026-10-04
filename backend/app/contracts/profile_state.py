"""A signed-in person's saved state: answers, change log, checklist and last coverage-type pop-up.

Shape matches ``frontend/src/services/profileStore.ts``. Every value is validated with the same
bounds the AI endpoints use; anything else is rejected rather than stored.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.ai import AskedField
from app.domain.compass import CompassProfile

MAX_LOG_ENTRIES = 50
MAX_STEPS = 20


class SavedAnswers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p: CompassProfile
    known: list[AskedField] = Field(default_factory=list, max_length=18)
    confirmed: bool = False
    # Milliseconds since the epoch, as the browser records it.
    updated: int | None = Field(default=None, ge=0)

    @field_validator("known")
    @classmethod
    def _unique(cls, value: list[AskedField]) -> list[AskedField]:
        return list(dict.fromkeys(value))


class LogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    at: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=300)


class ProfileState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saved: SavedAnswers
    log: list[LogEntry] = Field(default_factory=list, max_length=MAX_LOG_ENTRIES)
    steps: dict[str, bool] = Field(default_factory=dict, max_length=MAX_STEPS)
    policySeen: Literal["term", "perm"] | None = None

    @field_validator("steps")
    @classmethod
    def _step_keys(cls, value: dict[str, bool]) -> dict[str, bool]:
        if any(not 0 < len(key) <= 300 for key in value):
            raise ValueError("checklist items must be 1 to 300 characters")
        return value


class ProfileStateOut(BaseModel):
    # None until the person saves something for the first time.
    state: ProfileState | None
    updated_at: datetime | None
