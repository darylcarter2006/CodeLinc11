"""Callback requests for a licensed representative: validate, store, never log the details."""

from __future__ import annotations

import logging

from app.contracts.support import CallbackRequestIn
from app.repositories.callbacks import CallbackRecord, CallbackRepository
from app.security.tokens import new_id
from app.services.sessions import Clock

logger = logging.getLogger(__name__)


class SupportService:
    def __init__(self, repo: CallbackRepository, clock: Clock) -> None:
        self._repo = repo
        self._clock = clock

    async def request_callback(self, req: CallbackRequestIn, user_id: str | None) -> str:
        record = CallbackRecord(
            id=new_id("cbk"),
            name=req.name,
            contact_method=req.contactMethod,
            contact=req.contact,
            best_time=req.bestTime,
            topic=req.topic,
            summary=req.summary.model_dump() if req.summary else None,
            user_id=user_id,
            created_at=self._clock(),
        )
        await self._repo.add(record)
        # Contact details stay in the database; the log line only records that it happened.
        logger.info("callback_requested")
        return record.id
