"""Storage for callback requests (contact details, so treat as personal data)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CallbackRecord:
    id: str
    name: str
    contact_method: str
    contact: str
    best_time: str
    topic: str
    summary: dict[str, Any] | None
    user_id: str | None
    created_at: datetime


class CallbackRepository(ABC):
    @abstractmethod
    async def add(self, record: CallbackRecord) -> None: ...

    @abstractmethod
    async def delete_for_user(self, user_id: str) -> None: ...

    @abstractmethod
    async def purge(self, created_before: datetime) -> int:
        """Delete requests older than this; returns how many."""


class InMemoryCallbackRepository(CallbackRepository):
    """Local development and tests only."""

    def __init__(self) -> None:
        self.records: list[CallbackRecord] = []

    async def add(self, record: CallbackRecord) -> None:
        self.records.append(record)

    async def delete_for_user(self, user_id: str) -> None:
        self.records = [r for r in self.records if r.user_id != user_id]

    async def purge(self, created_before: datetime) -> int:
        before = len(self.records)
        self.records = [r for r in self.records if r.created_at >= created_before]
        return before - len(self.records)
