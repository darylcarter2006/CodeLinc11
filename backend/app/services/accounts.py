"""Google sign-in, account tokens, and sign-out."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.domain.users import AccountTokenRecord, UserRecord
from app.errors import (
    AuthNotConfigured,
    AuthProviderUnreachable,
    InvalidCredential,
    SessionExpired,
    Unauthorized,
)
from app.repositories.users import UserRepository
from app.security.google import GoogleTokenVerifier, GoogleUnreachable, InvalidGoogleToken
from app.security.redaction import log_safe_session_id
from app.security.tokens import generate_token, hash_token
from app.services.sessions import Clock

logger = logging.getLogger(__name__)


class AccountService:
    def __init__(
        self,
        users: UserRepository,
        verifier: GoogleTokenVerifier | None,
        token_ttl_hours: int,
        clock: Clock,
    ) -> None:
        self._users = users
        self._verifier = verifier
        self._ttl = timedelta(hours=token_ttl_hours)
        self._clock = clock

    async def sign_in_with_google(self, credential: str) -> tuple[UserRecord, str, datetime]:
        """Verify the Google credential; returns the user, a new raw token, and its expiry."""
        if self._verifier is None:
            raise AuthNotConfigured()
        try:
            profile = await self._verifier.verify(credential)
        except InvalidGoogleToken as exc:
            # The reason is logged for debugging; the client gets one generic message.
            logger.info("google_sign_in_rejected", extra={"error_code": str(exc)[:80]})
            raise InvalidCredential() from None
        except GoogleUnreachable:
            raise AuthProviderUnreachable() from None

        now = self._clock()
        user = await self._users.upsert_google_user(profile, now)
        raw_token = generate_token()
        expires_at = now + self._ttl
        await self._users.add_token(
            AccountTokenRecord(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                expires_at=expires_at,
                created_at=now,
            )
        )
        logger.info("google_sign_in", extra={"session_ref": log_safe_session_id(user.id)})
        return user, raw_token, expires_at

    async def authorize(self, raw_token: str | None) -> UserRecord:
        if raw_token is None:
            raise Unauthorized()
        token = await self._users.get_token(hash_token(raw_token))
        if token is None:
            raise Unauthorized()
        if token.expires_at <= self._clock():
            await self._users.delete_token(token.token_hash)
            raise SessionExpired("Your sign-in has expired. Please sign in again.")
        user = await self._users.get_user(token.user_id)
        if user is None:
            raise Unauthorized()
        return user

    async def sign_out(self, raw_token: str) -> None:
        await self._users.delete_token(hash_token(raw_token))
