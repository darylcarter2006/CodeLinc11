"""Google ID token checks: our claim rules, and how library errors are mapped."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from google.auth import exceptions
from google.oauth2 import id_token

from app.security.google import (
    GoogleAuthVerifier,
    GoogleUnreachable,
    InvalidGoogleToken,
    profile_from_claims,
)
from app.settings import Settings

CLIENT_ID = "123456789-abc.apps.googleusercontent.com"


def claims(**overrides: Any) -> dict[str, Any]:
    return {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "Jordan@Example.com",
        "email_verified": True,
        "name": "Jordan Lee",
        "given_name": "Jordan",
        "picture": "https://lh3.googleusercontent.com/a/x",
        **overrides,
    }


def test_valid_claims_become_a_profile() -> None:
    profile = profile_from_claims(claims(), CLIENT_ID, None)
    assert profile.sub == "1234567890"
    assert profile.email == "jordan@example.com"
    assert profile.given_name == "Jordan"


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-elses-app.apps.googleusercontent.com"},
        {"iss": "https://evil.example"},
        {"email_verified": False},
        {"email_verified": "true"},  # must be the boolean, not a string
        {"sub": ""},
        {"email": None},
    ],
)
def test_bad_claims_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(InvalidGoogleToken):
        profile_from_claims(claims(**overrides), CLIENT_ID, None)


def test_hosted_domain_restriction() -> None:
    assert profile_from_claims(claims(hd="example.com"), CLIENT_ID, "example.com")
    with pytest.raises(InvalidGoogleToken):
        profile_from_claims(claims(), CLIENT_ID, "example.com")  # personal Gmail account


def test_name_falls_back_to_email_prefix() -> None:
    profile = profile_from_claims(claims(name="  ", given_name=None), CLIENT_ID, None)
    assert profile.name == "jordan"
    assert profile.given_name is None


def _patch_library(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    def fake_verify(token: str, request: Any, audience: str, clock_skew_in_seconds: int) -> Any:
        assert audience == CLIENT_ID
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(id_token, "verify_oauth2_token", fake_verify)


def test_library_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_library(monkeypatch, claims())
    profile = asyncio.run(GoogleAuthVerifier(CLIENT_ID).verify("jwt"))
    assert profile.email == "jordan@example.com"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("Token expired"), InvalidGoogleToken),
        (exceptions.InvalidValue("bad signature"), InvalidGoogleToken),  # type: ignore[no-untyped-call]
        (exceptions.TransportError("no network"), GoogleUnreachable),  # type: ignore[no-untyped-call]
    ],
)
def test_library_errors_are_mapped(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: type[Exception]
) -> None:
    _patch_library(monkeypatch, error)
    with pytest.raises(expected):
        asyncio.run(GoogleAuthVerifier(CLIENT_ID).verify("jwt"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("", None), ("  ", None), (f" {CLIENT_ID} ", CLIENT_ID)],
)
def test_client_id_setting(value: str | None, expected: str | None) -> None:
    assert Settings(_env_file=None, google_client_id=value).google_client_id == expected


def test_client_id_setting_rejects_obvious_mistakes() -> None:
    with pytest.raises(ValueError, match=r"apps\.googleusercontent\.com"):
        Settings(_env_file=None, google_client_id="GOCSPX-this-is-a-client-secret")
