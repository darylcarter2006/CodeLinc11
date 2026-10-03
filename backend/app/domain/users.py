"""Signed-in accounts. Identity comes from Google; we store no passwords."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    # Google's stable account ID ("sub" claim). Emails can change; this does not.
    google_sub: str
    email: str
    name: str
    given_name: str | None = None
    picture: str | None = None
    created_at: datetime
    last_login_at: datetime


class AccountTokenRecord(BaseModel):
    """Bearer token for a signed-in user. Only the SHA-256 hash is stored."""

    model_config = ConfigDict(frozen=True)

    token_hash: str
    user_id: str
    expires_at: datetime
    created_at: datetime
