"""Account (Google sign-in) contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GoogleSignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The ID token (JWT) from Google Identity Services' callback: response.credential.
    credential: str = Field(min_length=20, max_length=4096)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    given_name: str | None
    picture: str | None


class SignInResponse(BaseModel):
    access_token: str
    expires_at: datetime
    user: UserOut
