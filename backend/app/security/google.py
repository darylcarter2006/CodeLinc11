"""Verify Google Identity Services ID tokens.

The browser receives a signed JWT (the "credential") from the Sign in with Google button
and sends it to us. We check Google's signature, that it was issued to *our* client ID,
that it hasn't expired, the issuer, and that the email is verified. Only then is the
person treated as signed in.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from app.repositories.users import GoogleProfile

GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})


class InvalidGoogleToken(Exception):
    """The credential is malformed, forged, expired, or for a different app."""


class GoogleUnreachable(Exception):
    """Google's signing keys could not be fetched."""


class GoogleTokenVerifier(ABC):
    @abstractmethod
    async def verify(self, credential: str) -> GoogleProfile:
        """Return the verified profile, or raise InvalidGoogleToken / GoogleUnreachable."""


def profile_from_claims(
    claims: dict[str, Any], client_id: str, hosted_domain: str | None
) -> GoogleProfile:
    """Apply our rules to already signature-checked claims."""
    if claims.get("aud") != client_id:
        raise InvalidGoogleToken("audience")
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleToken("issuer")
    if claims.get("email_verified") is not True:
        raise InvalidGoogleToken("email not verified")
    if hosted_domain is not None and claims.get("hd") != hosted_domain:
        raise InvalidGoogleToken("hosted domain")
    sub, email = claims.get("sub"), claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
        raise InvalidGoogleToken("missing claims")

    def text(key: str, limit: int) -> str | None:
        value = claims.get(key)
        if not isinstance(value, str):
            return None
        return value.strip()[:limit] or None

    email = email.strip().lower()
    return GoogleProfile(
        sub=sub,
        email=email,
        name=text("name", 120) or email.split("@")[0],
        given_name=text("given_name", 60),
        picture=text("picture", 500),
    )


class GoogleAuthVerifier(GoogleTokenVerifier):
    """Uses Google's official ``google-auth`` library to check the signature and expiry."""

    def __init__(self, client_id: str, hosted_domain: str | None = None) -> None:
        self._client_id = client_id
        self._hosted_domain = hosted_domain

    async def verify(self, credential: str) -> GoogleProfile:
        claims = await asyncio.to_thread(self._verify_sync, credential)
        return profile_from_claims(claims, self._client_id, self._hosted_domain)

    def _verify_sync(self, credential: str) -> dict[str, Any]:
        # Imported lazily so the app starts (and tests run) without network access.
        from google.auth import exceptions
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            claims: dict[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                credential,
                google_requests.Request(),
                audience=self._client_id,
                clock_skew_in_seconds=10,
            )
        except exceptions.TransportError as exc:
            raise GoogleUnreachable() from exc
        except (ValueError, exceptions.GoogleAuthError) as exc:
            raise InvalidGoogleToken(str(exc)) from exc
        return claims
