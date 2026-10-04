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


class InMemoryCallbackRepository(CallbackRepository):
    """Local development and tests only."""

    def __init__(self) -> None:
        self.records: list[CallbackRecord] = []

    async def add(self, record: CallbackRecord) -> None:
        self.records.append(record)
