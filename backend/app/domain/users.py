"""Signed-in accounts: email and password, Google, or both on one account."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    # Google's stable account ID ("sub" claim), once the account has signed in with Google.
    google_sub: str | None = None
    # Always stored lowercased; unique across accounts.
    email: str
    name: str
    given_name: str | None = None
    picture: str | None = None
    # Argon2id hash; None for Google-only accounts. Kept out of repr so it never reaches a log.
    password_hash: str | None = Field(default=None, repr=False)
    # True once Google confirmed the address, or a reset link sent to it was used.
    email_verified: bool = False
    created_at: datetime
    last_login_at: datetime


class AccountTokenRecord(BaseModel):
    """Bearer token for a signed-in user. Only the SHA-256 hash is stored."""

    model_config = ConfigDict(frozen=True)

    token_hash: str
    user_id: str
    expires_at: datetime
    created_at: datetime


class ResetTokenRecord(BaseModel):
    """Single-use password reset link. Only the SHA-256 hash is stored."""

    model_config = ConfigDict(frozen=True)

    token_hash: str
    user_id: str
    expires_at: datetime
    created_at: datetime
