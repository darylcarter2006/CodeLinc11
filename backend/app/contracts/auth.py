"""Account contracts: email and password, Google sign-in, password reset."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Generous enough for any passphrase; the password rules cap it at 128. Bounded here so a huge
# body can't make the server hash megabytes.
Password = Field(min_length=1, max_length=256)


def _email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value):
        raise ValueError("Enter a valid email address, like you@example.com.")
    return value


# Trimmed and lowercased, so one address always means one account.
Email = Annotated[str, Field(min_length=3, max_length=254), AfterValidator(_email)]


class GoogleSignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The ID token (JWT) from Google Identity Services' callback: response.credential.
    credential: str = Field(min_length=20, max_length=4096)


class SignUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    email: Email
    password: str = Password

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Enter your first name.")
        return value


class LogInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email
    password: str = Password


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Password
    new_password: str = Password


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Email


class PasswordResetConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(pattern=r"^[0-9a-f]{64}$")
    new_password: str = Password


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    given_name: str | None
    picture: str | None
    # Lets the front end offer "Change password" only to accounts that have one.
    has_password: bool


class SignInResponse(BaseModel):
    access_token: str
    expires_at: datetime
    user: UserOut
