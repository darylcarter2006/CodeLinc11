"""Storage for accounts, their sign-in tokens, and password reset links."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain.users import AccountTokenRecord, ResetTokenRecord, UserRecord
from app.security.tokens import new_id


@dataclass(frozen=True)
class GoogleProfile:
    """The verified claims we keep from a Google ID token."""

    sub: str
    email: str
    name: str
    given_name: str | None
    picture: str | None


class EmailTaken(Exception):
    """Another account already uses this email address."""


class UserRepository(ABC):
    @abstractmethod
    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        """Sign in with Google: find the account by Google ID, else link the account with the
        same email, else create one.

        Linking to an account whose email was never verified removes its password and signs
        out its sessions: whoever set that password hadn't proved they own the address.
        """

    @abstractmethod
    async def create_password_user(
        self, *, email: str, name: str, password_hash: str, now: datetime
    ) -> UserRecord:
        """Raises EmailTaken if the address is in use."""

    @abstractmethod
    async def get_user(self, user_id: str) -> UserRecord | None: ...

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserRecord | None: ...

    @abstractmethod
    async def set_password(self, user_id: str, password_hash: str, *, verify_email: bool) -> None:
        """Replace the password hash; ``verify_email`` also marks the address as confirmed."""

    @abstractmethod
    async def touch_login(self, user_id: str, now: datetime) -> None: ...

    @abstractmethod
    async def add_token(self, token: AccountTokenRecord) -> None: ...

    @abstractmethod
    async def get_token(self, token_hash: str) -> AccountTokenRecord | None: ...

    @abstractmethod
    async def delete_token(self, token_hash: str) -> None: ...

    @abstractmethod
    async def delete_user_tokens(self, user_id: str, *, keep: str | None = None) -> None:
        """Sign the account out everywhere, except the token hash in ``keep``."""

    @abstractmethod
    async def add_reset_token(self, token: ResetTokenRecord) -> None: ...

    @abstractmethod
    async def delete_user(self, user_id: str) -> None:
        """Delete the account and everything stored under it (tokens, reset links, saved state)."""

    @abstractmethod
    async def purge(self, now: datetime, inactive_before: datetime) -> int:
        """Delete expired tokens and reset links, and accounts not signed in to since
        ``inactive_before``. Returns how many accounts were deleted."""

    @abstractmethod
    async def consume_reset_token(self, token_hash: str, now: datetime) -> str | None:
        """Use a reset link once: returns its user ID if it is valid, and deletes every reset
        link that user has. Returns None for an unknown, used or expired link."""


class InMemoryUserRepository(UserRepository):
    """Single-process store for local development and tests."""

    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._tokens: dict[str, AccountTokenRecord] = {}
        self._resets: dict[str, ResetTokenRecord] = {}

    def _find(self, *, email: str | None = None, sub: str | None = None) -> UserRecord | None:
        for user in self._users.values():
            if (email is not None and user.email == email) or (
                sub is not None and user.google_sub == sub
            ):
                return user
        return None

    async def upsert_google_user(self, profile: GoogleProfile, now: datetime) -> UserRecord:
        existing = self._find(sub=profile.sub)
        if existing is not None:
            other = self._find(email=profile.email)
            email = profile.email if other is None or other.id == existing.id else existing.email
            user = existing.model_copy(
                update={
                    "email": email,
                    "name": profile.name,
                    "given_name": profile.given_name,
                    "picture": profile.picture,
                    "email_verified": existing.email_verified or email == profile.email,
                    "last_login_at": now,
                }
            )
        elif (by_email := self._find(email=profile.email)) is not None:
            unverified_password = by_email.password_hash is not None and not by_email.email_verified
            if unverified_password:
                await self.delete_user_tokens(by_email.id)
            user = by_email.model_copy(
                update={
                    "google_sub": profile.sub,
                    "picture": by_email.picture or profile.picture,
                    "password_hash": None if unverified_password else by_email.password_hash,
                    "email_verified": True,
                    "last_login_at": now,
                }
            )
        else:
            user = UserRecord(
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
        self._users[user.id] = user
        return user

    async def create_password_user(
        self, *, email: str, name: str, password_hash: str, now: datetime
    ) -> UserRecord:
        if self._find(email=email) is not None:
            raise EmailTaken()
        user = UserRecord(
            id=new_id("usr"),
            email=email,
            name=name,
            given_name=name,
            password_hash=password_hash,
            created_at=now,
            last_login_at=now,
        )
        self._users[user.id] = user
        return user

    async def get_user(self, user_id: str) -> UserRecord | None:
        return self._users.get(user_id)

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._find(email=email)

    async def set_password(self, user_id: str, password_hash: str, *, verify_email: bool) -> None:
        user = self._users[user_id]
        self._users[user_id] = user.model_copy(
            update={
                "password_hash": password_hash,
                "email_verified": user.email_verified or verify_email,
            }
        )

    async def touch_login(self, user_id: str, now: datetime) -> None:
        self._users[user_id] = self._users[user_id].model_copy(update={"last_login_at": now})

    async def add_token(self, token: AccountTokenRecord) -> None:
        self._tokens[token.token_hash] = token

    async def get_token(self, token_hash: str) -> AccountTokenRecord | None:
        return self._tokens.get(token_hash)

    async def delete_token(self, token_hash: str) -> None:
        self._tokens.pop(token_hash, None)

    async def delete_user_tokens(self, user_id: str, *, keep: str | None = None) -> None:
        self._tokens = {h: t for h, t in self._tokens.items() if t.user_id != user_id or h == keep}

    async def add_reset_token(self, token: ResetTokenRecord) -> None:
        self._resets[token.token_hash] = token

    async def delete_user(self, user_id: str) -> None:
        self._users.pop(user_id, None)
        self._tokens = {h: t for h, t in self._tokens.items() if t.user_id != user_id}
        self._resets = {h: t for h, t in self._resets.items() if t.user_id != user_id}

    async def purge(self, now: datetime, inactive_before: datetime) -> int:
        self._tokens = {h: t for h, t in self._tokens.items() if t.expires_at > now}
        self._resets = {h: t for h, t in self._resets.items() if t.expires_at > now}
        stale = [u.id for u in self._users.values() if u.last_login_at < inactive_before]
        for user_id in stale:
            await self.delete_user(user_id)
        return len(stale)

    async def consume_reset_token(self, token_hash: str, now: datetime) -> str | None:
        token = self._resets.get(token_hash)
        if token is None or token.expires_at <= now:
            return None
        self._resets = {h: t for h, t in self._resets.items() if t.user_id != token.user_id}
        return token.user_id
