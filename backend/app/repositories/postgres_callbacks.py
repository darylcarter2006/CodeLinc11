"""PostgreSQL implementation of CallbackRepository (table from migration 0004)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete

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

    async def delete_for_user(self, user_id: str) -> None:
        async with db_session() as db:
            await db.execute(
                delete(CallbackRequestRow).where(CallbackRequestRow.user_id == user_id)
            )

    async def purge(self, created_before: datetime) -> int:
        async with db_session() as db:
            deleted = await db.execute(
                delete(CallbackRequestRow)
                .where(CallbackRequestRow.created_at < created_before)
                .returning(CallbackRequestRow.id)
            )
            return len(deleted.all())
