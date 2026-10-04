"""Accounts: email and password, Google sign-in, account tokens, and password reset."""

from __future__ import annotations

import html
import logging
from datetime import datetime, timedelta

from app.domain.users import AccountTokenRecord, ResetTokenRecord, UserRecord
from app.errors import (
    AuthNotConfigured,
    AuthProviderUnreachable,
    EmailInUse,
    InvalidCredential,
    InvalidLogin,
    PasswordNotSet,
    ResetLinkInvalid,
    ResetUnavailable,
    SessionExpired,
    Unauthorized,
    WeakPassword,
)
from app.notifications.email import EmailMessage
from app.repositories.users import EmailTaken, UserRepository
from app.security.google import GoogleTokenVerifier, GoogleUnreachable, InvalidGoogleToken
from app.security.passwords import hash_password, needs_rehash, password_problem, verify_password
from app.security.rate_limit import RateLimiter
from app.security.redaction import log_safe_session_id
from app.security.tokens import generate_token, hash_token
from app.services.sessions import Clock

logger = logging.getLogger(__name__)

SignIn = tuple[UserRecord, str, datetime]


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AccountService:
    def __init__(
        self,
        users: UserRepository,
        verifier: GoogleTokenVerifier | None,
        token_ttl_hours: int,
        clock: Clock,
        *,
        login_limiter: RateLimiter | None = None,
        reset_limiter: RateLimiter | None = None,
        reset_base_url: str | None = None,
        reset_ttl_minutes: int = 30,
    ) -> None:
        self._users = users
        self._verifier = verifier
        self._ttl = timedelta(hours=token_ttl_hours)
        self._clock = clock
        # Per email address, so guessing one account's password from many IPs is still capped.
        self._login_limiter = login_limiter or RateLimiter(10, window_seconds=15 * 60)
        self._reset_limiter = reset_limiter or RateLimiter(3, window_seconds=60 * 60)
        # None means password reset email is off.
        self._reset_base_url = reset_base_url
        self._reset_ttl = timedelta(minutes=reset_ttl_minutes)

    async def _issue_token(self, user: UserRecord) -> SignIn:
        now = self._clock()
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
        return user, raw_token, expires_at

    async def sign_in_with_google(self, credential: str) -> SignIn:
        """Verify the Google credential; returns the user, a new raw token, and its expiry."""
        if self._verifier is None:
            raise AuthNotConfigured()
        try:
            profile = await self._verifier.verify(credential)
        except InvalidGoogleToken as exc:
            # A short, fixed reason is logged for debugging (never token text); the client gets
            # one generic message.
            logger.info("google_sign_in_rejected", extra={"error_code": str(exc)[:40]})
            raise InvalidCredential() from None
        except GoogleUnreachable:
            raise AuthProviderUnreachable() from None

        user = await self._users.upsert_google_user(profile, self._clock())
        logger.info("google_sign_in", extra={"session_ref": log_safe_session_id(user.id)})
        return await self._issue_token(user)

    async def sign_up(self, name: str, email: str, password: str) -> SignIn:
        email = normalize_email(email)
        if problem := password_problem(password, email):
            raise WeakPassword(problem)
        try:
            user = await self._users.create_password_user(
                email=email,
                name=name.strip(),
                password_hash=hash_password(password),
                now=self._clock(),
            )
        except EmailTaken:
            raise EmailInUse() from None
        logger.info("password_sign_up", extra={"session_ref": log_safe_session_id(user.id)})
        return await self._issue_token(user)

    async def log_in(self, email: str, password: str) -> SignIn:
        email = normalize_email(email)
        self._login_limiter.check(email)
        user = await self._users.get_user_by_email(email)
        # Always runs a full hash check, so an unknown email takes as long as a wrong password.
        if not verify_password(user.password_hash if user else None, password) or user is None:
            logger.info("password_log_in_rejected")
            raise InvalidLogin()
        assert user.password_hash is not None  # verify_password() is False without a hash
        if needs_rehash(user.password_hash):
            await self._users.set_password(user.id, hash_password(password), verify_email=False)
        await self._users.touch_login(user.id, self._clock())
        logger.info("password_log_in", extra={"session_ref": log_safe_session_id(user.id)})
        return await self._issue_token(user)

    async def change_password(
        self, user: UserRecord, raw_token: str, current: str, new: str
    ) -> None:
        """Change the password; every other signed-in device is signed out."""
        if user.password_hash is None:
            raise PasswordNotSet()
        if not verify_password(user.password_hash, current):
            raise InvalidLogin("Your current password isn't right.")
        if problem := password_problem(new, user.email):
            raise WeakPassword(problem)
        await self._users.set_password(user.id, hash_password(new), verify_email=False)
        await self._users.delete_user_tokens(user.id, keep=hash_token(raw_token))
        logger.info("password_changed", extra={"session_ref": log_safe_session_id(user.id)})

    async def request_password_reset(self, email: str) -> EmailMessage | None:
        """Make a reset link if the account exists. The caller sends the returned email in the
        background and answers the same way either way, so the response never reveals whether
        an address has an account."""
        if self._reset_base_url is None:
            raise ResetUnavailable()
        email = normalize_email(email)
        self._reset_limiter.check(email)
        user = await self._users.get_user_by_email(email)
        if user is None:
            return None
        now = self._clock()
        raw_token = generate_token()
        await self._users.add_reset_token(
            ResetTokenRecord(
                token_hash=hash_token(raw_token),
                user_id=user.id,
                expires_at=now + self._reset_ttl,
                created_at=now,
            )
        )
        logger.info("password_reset_requested", extra={"session_ref": log_safe_session_id(user.id)})
        # The token goes after "#", so it never reaches a server log or a Referer header.
        return _reset_email(
            user, f"{self._reset_base_url}/reset-password#token={raw_token}", self._reset_ttl
        )

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> SignIn:
        """Use a reset link: set the new password, sign out everywhere else, and sign in."""
        # Checked before the link is used up, so a rejected password doesn't waste the link.
        if problem := password_problem(new_password, ""):
            raise WeakPassword(problem)
        user_id = await self._users.consume_reset_token(hash_token(raw_token), self._clock())
        user = await self._users.get_user(user_id) if user_id else None
        if user is None:
            raise ResetLinkInvalid()
        if problem := password_problem(new_password, user.email):
            raise WeakPassword(problem + " Request a new reset link to try again.")
        # Using a link sent to the address proves the person owns it.
        await self._users.set_password(user.id, hash_password(new_password), verify_email=True)
        await self._users.delete_user_tokens(user.id)
        await self._users.touch_login(user.id, self._clock())
        logger.info("password_reset", extra={"session_ref": log_safe_session_id(user.id)})
        return await self._issue_token(user)

    def confirm_password(self, user: UserRecord, password: str | None) -> None:
        """Re-check the password before something that can't be undone. Google-only accounts
        have none; for them the signed-in token is the check."""
        if user.password_hash is not None and not verify_password(
            user.password_hash, password or ""
        ):
            raise InvalidLogin("Your password isn't right.")

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


def _reset_email(user: UserRecord, link: str, ttl: timedelta) -> EmailMessage:
    minutes = int(ttl.total_seconds() // 60)
    name = user.given_name or user.name
    text = (
        f"Hi {name},\n\n"
        "Someone asked to reset the password for your Coverage Compass account. To choose a new "
        f"password, open this link within {minutes} minutes:\n\n{link}\n\n"
        "The link works once. If you didn't ask for this, you can ignore this email; your "
        "password won't change.\n\nCoverage Compass from Lincoln Financial"
    )
    safe_link = html.escape(link, quote=True)
    body = (
        f"<p>Hi {html.escape(name)},</p>"
        "<p>Someone asked to reset the password for your Coverage Compass account. To choose a "
        f"new password, open this link within {minutes} minutes:</p>"
        f'<p><a href="{safe_link}">Choose a new password</a></p>'
        "<p>The link works once. If you didn't ask for this, you can ignore this email; your "
        "password won't change.</p><p>Coverage Compass from Lincoln Financial</p>"
    )
    return EmailMessage(
        to=user.email, subject="Reset your Coverage Compass password", text=text, html=body
    )
