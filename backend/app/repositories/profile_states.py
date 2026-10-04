"""Storage for each signed-in person's saved state (see app/contracts/profile_state.py)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class ProfileStateRepository(ABC):
    @abstractmethod
    async def get(self, user_id: str) -> tuple[dict[str, Any], datetime] | None: ...

    @abstractmethod
    async def put(self, user_id: str, data: dict[str, Any], now: datetime) -> None: ...


class InMemoryProfileStateRepository(ProfileStateRepository):
    """Local development and tests only."""

    def __init__(self) -> None:
        self._states: dict[str, tuple[dict[str, Any], datetime]] = {}

    async def get(self, user_id: str) -> tuple[dict[str, Any], datetime] | None:
        return self._states.get(user_id)

    async def put(self, user_id: str, data: dict[str, Any], now: datetime) -> None:
        self._states[user_id] = (data, now)
