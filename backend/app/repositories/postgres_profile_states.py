"""PostgreSQL implementation of ProfileStateRepository (table from migration 0005)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import ProfileStateRow
from app.db.session import db_session
from app.repositories.profile_states import ProfileStateRepository


class PostgresProfileStateRepository(ProfileStateRepository):
    async def get(self, user_id: str) -> tuple[dict[str, Any], datetime] | None:
        async with db_session() as db:
            row = await db.get(ProfileStateRow, user_id)
            return (row.data, row.updated_at) if row is not None else None  # type: ignore[return-value]

    async def put(self, user_id: str, data: dict[str, Any], now: datetime) -> None:
        async with db_session() as db:
            await db.execute(
                pg_insert(ProfileStateRow)
                .values(user_id=user_id, data=data, updated_at=now)
                .on_conflict_do_update(
                    index_elements=["user_id"], set_={"data": data, "updated_at": now}
                )
            )
