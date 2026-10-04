"""PostgreSQL implementation of CallbackRepository (table from migration 0004)."""

from __future__ import annotations

from app.db.models import CallbackRequestRow
from app.db.session import db_session
from app.repositories.callbacks import CallbackRecord, CallbackRepository


class PostgresCallbackRepository(CallbackRepository):
    async def add(self, record: CallbackRecord) -> None:
        async with db_session() as db:
            db.add(
                CallbackRequestRow(
                    id=record.id,
                    name=record.name,
                    contact_method=record.contact_method,
                    contact=record.contact,
                    best_time=record.best_time,
                    topic=record.topic,
                    summary=record.summary,
                    user_id=record.user_id,
                    created_at=record.created_at,
                )
            )
