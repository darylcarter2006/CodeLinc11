"""PostgreSQL implementation of UserRepository (tables from migrations 0003 and 0005)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AccountTokenRow, PasswordResetTokenRow, UserRow
from app.db.session import db_session
from app.domain.users import AccountTokenRecord, ResetTokenRecord, UserRecord
from app.repositories.users import EmailTaken, GoogleProfile, UserRepository
from app.security.tokens import new_id


def _user_from_row(row: UserRow) -> UserRecord:
    return UserRecord(
        id=row.id,
        google_sub=row.google_sub,
        email=row.email,
        name=row.name,
        given_name=row.given_name,
        picture=row.picture,
        password_hash=row.password_hash,
        email_verified=row.email_verified,
        created_at=row.created_at,
        last_login_at=row.last_login_at,
    )


async def _locked(db: AsyncSession, *conditions: object) -> UserRow | None:
    statement = select(UserRow).where(*conditions).with_for_update()  # type: ignore[arg-type]
    return (await db.execute(statement)).scalar_one_or_none()


class PostgresUserRepository(UserRepository):
    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        # A simultaneous first sign-in can insert the same person between our check and our
        # insert; the second attempt then finds that row.
        for _ in range(2):
            user = await self._upsert_google_once(profile, now)
            if user is not None:
                return user
        raise RuntimeError("Google sign-in kept conflicting with another sign-in")

    async def _upsert_google_once(self, profile: GoogleProfile, now: datetime) -> UserRecord | None:
        async with db_session() as db:
            row = await _locked(db, UserRow.google_sub == profile.sub)
            if row is not None:
                taken = await db.scalar(
                    select(UserRow.id).where(UserRow.email == profile.email, UserRow.id != row.id)
                )
                if taken is None:
                    row.email = profile.email
                    row.email_verified = True
                row.name = profile.name
                row.given_name = profile.given_name
                row.picture = profile.picture
                row.last_login_at = now
                return _user_from_row(row)

            row = await _locked(db, UserRow.email == profile.email)
            if row is not None:
                if row.password_hash is not None and not row.email_verified:
                    # Whoever set this password never proved they own the address.
                    row.password_hash = None
                    await db.execute(
                        delete(AccountTokenRow).where(AccountTokenRow.user_id == row.id)
                    )
                row.google_sub = profile.sub
                row.picture = row.picture or profile.picture
                row.email_verified = True
                row.last_login_at = now
                return _user_from_row(row)

            inserted = (
                await db.execute(
                    pg_insert(UserRow)
                    .values(
                        id=new_id("usr"),
                        google_sub=profile.sub,
                        email=profile.email,
                        name=profile.name,
                        given_name=profile.given_name,
                        picture=profile.picture,
                        email_verified=True,
                        created_at=now,
                        last_login_at=now,
                    )
                    .on_conflict_do_nothing()
                    .returning(UserRow)
                )
            ).scalar_one_or_none()
            return _user_from_row(inserted) if inserted is not None else None

    async def create_password_user(
        self, *, email: str, name: str, password_hash: str, now: datetime
    ) -> UserRecord:
        async with db_session() as db:
            row = (
                await db.execute(
                    pg_insert(UserRow)
                    .values(
                        id=new_id("usr"),
                        email=email,
                        name=name,
                        given_name=name,
                        password_hash=password_hash,
                        email_verified=False,
                        created_at=now,
                        last_login_at=now,
                    )
                    .on_conflict_do_nothing(constraint="uq_users_email")
                    .returning(UserRow)
                )
            ).scalar_one_or_none()
            if row is None:
                raise EmailTaken()
            return _user_from_row(row)

    async def get_user(self, user_id: str) -> UserRecord | None:
        async with db_session() as db:
            row = await db.get(UserRow, user_id)
            return _user_from_row(row) if row is not None else None

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with db_session() as db:
            row = await db.scalar(select(UserRow).where(UserRow.email == email))
            return _user_from_row(row) if row is not None else None

    async def set_password(self, user_id: str, password_hash: str, *, verify_email: bool) -> None:
        values: dict[str, object] = {"password_hash": password_hash}
        if verify_email:
            values["email_verified"] = True
        async with db_session() as db:
            await db.execute(update(UserRow).where(UserRow.id == user_id).values(**values))

    async def touch_login(self, user_id: str, now: datetime) -> None:
        async with db_session() as db:
            await db.execute(update(UserRow).where(UserRow.id == user_id).values(last_login_at=now))

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

    async def delete_user_tokens(self, user_id: str, *, keep: str | None = None) -> None:
        statement = delete(AccountTokenRow).where(AccountTokenRow.user_id == user_id)
        if keep is not None:
            statement = statement.where(AccountTokenRow.token_hash != keep)
        async with db_session() as db:
            await db.execute(statement)

    async def add_reset_token(self, token: ResetTokenRecord) -> None:
        async with db_session() as db:
            db.add(
                PasswordResetTokenRow(
                    token_hash=token.token_hash,
                    user_id=token.user_id,
                    expires_at=token.expires_at,
                    created_at=token.created_at,
                )
            )

    async def delete_user(self, user_id: str) -> None:
        async with db_session() as db:
            # Tokens, reset links and saved state go with it (ON DELETE CASCADE).
            await db.execute(delete(UserRow).where(UserRow.id == user_id))

    async def purge(self, now: datetime, inactive_before: datetime) -> int:
        async with db_session() as db:
            await db.execute(delete(AccountTokenRow).where(AccountTokenRow.expires_at <= now))
            await db.execute(
                delete(PasswordResetTokenRow).where(PasswordResetTokenRow.expires_at <= now)
            )
            deleted = await db.execute(
                delete(UserRow).where(UserRow.last_login_at < inactive_before).returning(UserRow.id)
            )
            return len(deleted.all())

    async def consume_reset_token(self, token_hash: str, now: datetime) -> str | None:
        async with db_session() as db:
            # Deleting returns the link only once, even if it is used twice at the same moment.
            user_id = await db.scalar(
                delete(PasswordResetTokenRow)
                .where(
                    PasswordResetTokenRow.token_hash == token_hash,
                    PasswordResetTokenRow.expires_at > now,
                )
                .returning(PasswordResetTokenRow.user_id)
            )
            if user_id is not None:
                await db.execute(
                    delete(PasswordResetTokenRow).where(PasswordResetTokenRow.user_id == user_id)
                )
            return user_id
