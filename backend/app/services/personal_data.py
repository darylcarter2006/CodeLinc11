"""Deleting personal data: when someone asks, and on schedule (docs/data-handling.md)."""

from __future__ import annotations

import logging
from datetime import timedelta

from app.repositories.callbacks import CallbackRepository
from app.repositories.users import UserRepository
from app.services.sessions import Clock

logger = logging.getLogger(__name__)


class PersonalDataService:
    def __init__(
        self,
        users: UserRepository,
        callbacks: CallbackRepository,
        clock: Clock,
        *,
        account_retention_days: int,
        callback_retention_days: int,
    ) -> None:
        self._users = users
        self._callbacks = callbacks
        self._clock = clock
        self._account_retention = timedelta(days=account_retention_days)
        self._callback_retention = timedelta(days=callback_retention_days)

    async def delete_account(self, user_id: str) -> None:
        """Delete the account and everything kept for it: saved answers, sign-ins, reset links,
        and callback requests sent while signed in."""
        await self._callbacks.delete_for_user(user_id)
        await self._users.delete_user(user_id)
        logger.info("account_deleted")

    async def sweep(self) -> tuple[int, int]:
        """Delete what has outlived its retention period. Returns (accounts, callback requests)."""
        now = self._clock()
        accounts = await self._users.purge(now, inactive_before=now - self._account_retention)
        callbacks = await self._callbacks.purge(created_before=now - self._callback_retention)
        logger.info("retention_sweep")
        return accounts, callbacks
