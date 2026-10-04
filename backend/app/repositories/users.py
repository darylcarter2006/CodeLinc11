"""Storage for signed-in users and their account tokens."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain.users import AccountTokenRecord, UserRecord
from app.security.tokens import new_id


@dataclass(frozen=True)
class GoogleProfile:
    """The verified claims we keep from a Google ID token."""

    sub: str
    email: str
    name: str
    given_name: str | None
    picture: str | None


class UserRepository(ABC):
    @abstractmethod
    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        """Create the user on first sign-in; refresh email, name and picture afterwards."""

    @abstractmethod
    async def get_user(self, user_id: str) -> UserRecord | None: ...

    @abstractmethod
    async def add_token(self, token: AccountTokenRecord) -> None: ...

    @abstractmethod
    async def get_token(self, token_hash: str) -> AccountTokenRecord | None: ...

    @abstractmethod
    async def delete_token(self, token_hash: str) -> None: ...


class InMemoryUserRepository(UserRepository):
    """Single-process store for local development and tests."""

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._by_sub: dict[str, str] = {}
        self._tokens: dict[str, AccountTokenRecord] = {}

    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        user_id = self._by_sub.get(profile.sub)
        existing = self._users.get(user_id) if user_id else None
        user = UserRecord(
            id=existing.id if existing else new_id("usr"),
            google_sub=profile.sub,
            email=profile.email,
            name=profile.name,
            given_name=profile.given_name,
            picture=profile.picture,
            created_at=existing.created_at if existing else now,
            last_login_at=now,
        )
        self._users[user.id] = user
        self._by_sub[profile.sub] = user.id
        return user

    async def get_user(self, user_id: str) -> UserRecord | None:
        return self._users.get(user_id)

    async def add_token(self, token: AccountTokenRecord) -> None:
        self._tokens[token.token_hash] = token

    async def get_token(self, token_hash: str) -> AccountTokenRecord | None:
        return self._tokens.get(token_hash)

    async def delete_token(self, token_hash: str) -> None:
        self._tokens.pop(token_hash, None)
