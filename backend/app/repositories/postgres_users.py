"""PostgreSQL implementation of UserRepository (tables from migration 0003)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import AccountTokenRow, UserRow
from app.db.session import db_session
from app.domain.users import AccountTokenRecord, UserRecord
from app.repositories.users import GoogleProfile, UserRepository
from app.security.tokens import new_id


def _user_from_row(row: UserRow) -> UserRecord:
    return UserRecord(
        id=row.id,
        google_sub=row.google_sub,
        email=row.email,
        name=row.name,
        given_name=row.given_name,
        picture=row.picture,
        created_at=row.created_at,
        last_login_at=row.last_login_at,
    )


class PostgresUserRepository(UserRepository):
    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        async with db_session() as db:
            # One statement, so two simultaneous first sign-ins cannot create two users.
            statement = (
                pg_insert(UserRow)
                .values(
                    id=new_id("usr"),
                    google_sub=profile.sub,
                    email=profile.email,
                    name=profile.name,
                    given_name=profile.given_name,
                    picture=profile.picture,
                    created_at=now,
                    last_login_at=now,
                )
                .on_conflict_do_update(
                    constraint="uq_users_google_sub",
                    set_={
                        "email": profile.email,
                        "name": profile.name,
                        "given_name": profile.given_name,
                        "picture": profile.picture,
                        "last_login_at": now,
                    },
                )
                .returning(UserRow)
            )
            row = (await db.execute(statement)).scalar_one()
            return _user_from_row(row)

    async def get_user(self, user_id: str) -> UserRecord | None:
        async with db_session() as db:
            row = await db.get(UserRow, user_id)
            return _user_from_row(row) if row is not None else None

    async def add_token(self, token: AccountTokenRecord) -> None:
        async with db_session() as db:
            db.add(
                AccountTokenRow(
                    token_hash=token.token_hash,
                    user_id=token.user_id,
                    expires_at=token.expires_at,
                    created_at=token.created_at,
                )
            )

    async def get_token(self, token_hash: str) -> AccountTokenRecord | None:
        async with db_session() as db:
            row = await db.get(AccountTokenRow, token_hash)
            if row is None:
                return None
            return AccountTokenRecord(
                token_hash=row.token_hash,
                user_id=row.user_id,
                expires_at=row.expires_at,
                created_at=row.created_at,
            )

    async def delete_token(self, token_hash: str) -> None:
        async with db_session() as db:
            await db.execute(
                delete(AccountTokenRow).where(AccountTokenRow.token_hash == token_hash)
            )
