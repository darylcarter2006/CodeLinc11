"""Email and password accounts, password reset by email, and linking with Google sign-in."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.notifications.email import OutboxEmailSender
from app.repositories.users import InMemoryUserRepository
from tests.conftest import FakeClock
from tests.fakes import FakeGoogleVerifier

CLIENT_ID = "123456789-abc.apps.googleusercontent.com"
PASSWORD = "correct horse battery"
NEW_PASSWORD = "a brand new passphrase"


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        google_verifier=FakeGoogleVerifier(),
        google_client_id=CLIENT_ID,
        email_provider="outbox",
        app_base_url="http://localhost:5173",
        auth_rate_limit_per_minute=1000,
    )


def sign_up(client: TestClient, email: str = "Riley@Example.com", **overrides: Any) -> Any:
    body = {"name": "Riley", "email": email, "password": PASSWORD, **overrides}
    return client.post("/v1/auth/signup", json=body)


def log_in(client: TestClient, email: str = "riley@example.com", password: str = PASSWORD) -> Any:
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def outbox(client: TestClient) -> OutboxEmailSender:
    sender = client.app.state.container.email  # type: ignore[attr-defined]
    assert isinstance(sender, OutboxEmailSender)
    return sender


def reset_token(client: TestClient) -> str:
    match = re.search(r"/reset-password#token=([0-9a-f]{64})", outbox(client).outbox[-1].text)
    assert match is not None
    return match.group(1)


# --- sign-up and log-in ---


def test_sign_up_signs_in_with_a_lowercased_email(client: TestClient) -> None:
    response = sign_up(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["email"] == "riley@example.com"
    assert body["user"]["has_password"] is True
    me = client.get("/v1/auth/me", headers=bearer(body["access_token"]))
    assert me.json()["email"] == "riley@example.com"


def test_password_is_stored_only_as_an_argon2id_hash(client: TestClient) -> None:
    sign_up(client)
    users = client.app.state.container.accounts._users  # type: ignore[attr-defined]
    if not isinstance(users, InMemoryUserRepository):
        pytest.skip("inspects the in-memory store")
    [user] = users._users.values()
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash
    assert "argon2" not in repr(user)


def test_the_same_email_cannot_sign_up_twice(client: TestClient) -> None:
    assert sign_up(client).status_code == 201
    again = sign_up(client, email="  RILEY@example.COM ")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("short", "at least 8"),
        ("password123", "too easy"),
        ("aaaaaaaaaaaa", "too easy"),
        ("riley@example.com", "can't be your email"),
        ("x" * 129, "at most 128"),
    ],
)
def test_weak_passwords_are_rejected(client: TestClient, password: str, message: str) -> None:
    response = sign_up(client, password=password)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "weak_password"
    assert message in response.json()["error"]["message"]


def test_sign_up_validates_name_and_email(client: TestClient) -> None:
    assert sign_up(client, email="not-an-email").status_code == 422
    assert sign_up(client, name="   ").status_code == 422
    assert sign_up(client, password="x" * 257).status_code == 422


def test_log_in_with_the_right_password(client: TestClient) -> None:
    sign_up(client)
    response = log_in(client, email=" RILEY@example.com")
    assert response.status_code == 200
    assert client.get("/v1/auth/me", headers=bearer(response.json()["access_token"])).is_success


def test_wrong_password_and_unknown_email_get_the_same_answer(client: TestClient) -> None:
    sign_up(client)
    wrong = log_in(client, password="not the password")
    unknown = log_in(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_login"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_log_in_attempts_are_limited_per_email(make_client: Callable[..., TestClient]) -> None:
    client = make_client(login_attempts_per_email=3, auth_rate_limit_per_minute=1000)
    sign_up(client)
    for _ in range(3):
        assert log_in(client, password="wrong guess!").status_code == 401
    # Even the right password waits once the address has been guessed at too often.
    assert log_in(client).status_code == 429
    assert log_in(client, email="someone-else@example.com").status_code == 401


def test_sign_out_revokes_the_token(client: TestClient) -> None:
    token = sign_up(client).json()["access_token"]
    assert client.post("/v1/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/v1/auth/me", headers=bearer(token)).status_code == 401


# --- change password ---


def test_change_password_signs_out_other_devices(client: TestClient) -> None:
    here = sign_up(client).json()["access_token"]
    elsewhere = log_in(client).json()["access_token"]
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    assert client.post("/v1/auth/password", json=body, headers=bearer(here)).status_code == 204

    assert client.get("/v1/auth/me", headers=bearer(here)).is_success
    assert client.get("/v1/auth/me", headers=bearer(elsewhere)).status_code == 401
    assert log_in(client).status_code == 401
    assert log_in(client, password=NEW_PASSWORD).status_code == 200


def test_change_password_needs_the_current_one(client: TestClient) -> None:
    token = sign_up(client).json()["access_token"]
    body = {"current_password": "not it at all", "new_password": NEW_PASSWORD}
    response = client.post("/v1/auth/password", json=body, headers=bearer(token))
    assert response.status_code == 401
    assert client.post("/v1/auth/password", json=body).status_code == 401  # not signed in


def test_change_password_rejects_a_weak_new_one(client: TestClient) -> None:
    token = sign_up(client).json()["access_token"]
    body = {"current_password": PASSWORD, "new_password": "short"}
    response = client.post("/v1/auth/password", json=body, headers=bearer(token))
    assert response.json()["error"]["code"] == "weak_password"


def test_google_only_account_has_no_password_to_change(client: TestClient) -> None:
    google = client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"})
    token = google.json()["access_token"]
    body = {"current_password": "anything goes", "new_password": NEW_PASSWORD}
    response = client.post("/v1/auth/password", json=body, headers=bearer(token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "password_not_set"


# --- password reset ---


def test_reset_is_off_without_email(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    response = client.post("/v1/auth/password-reset/request", json={"email": "a@example.com"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "reset_unavailable"


def test_reset_request_answers_the_same_for_unknown_addresses(client: TestClient) -> None:
    response = client.post("/v1/auth/password-reset/request", json={"email": "no@example.com"})
    assert response.status_code == 202
    assert outbox(client).outbox == []


def test_reset_flow_sets_a_new_password_and_signs_out_everywhere(client: TestClient) -> None:
    old_token = sign_up(client).json()["access_token"]
    request = client.post("/v1/auth/password-reset/request", json={"email": "RILEY@example.com"})
    assert request.status_code == 202
    [message] = outbox(client).outbox
    assert message.to == "riley@example.com"
    assert "http://localhost:5173/reset-password#token=" in message.text
    token = reset_token(client)
    assert token in message.html

    confirm = client.post(
        "/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert confirm.status_code == 200
    assert client.get("/v1/auth/me", headers=bearer(confirm.json()["access_token"])).is_success
    assert client.get("/v1/auth/me", headers=bearer(old_token)).status_code == 401
    assert log_in(client).status_code == 401
    assert log_in(client, password=NEW_PASSWORD).status_code == 200

    reused = client.post(
        "/v1/auth/password-reset/confirm", json={"token": token, "new_password": PASSWORD}
    )
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "reset_link_invalid"


def test_reset_link_expires(client: TestClient, clock: FakeClock) -> None:
    sign_up(client)
    client.post("/v1/auth/password-reset/request", json={"email": "riley@example.com"})
    clock.advance(minutes=31)
    confirm = client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": reset_token(client), "new_password": NEW_PASSWORD},
    )
    assert confirm.status_code == 400


def test_a_weak_password_does_not_use_up_the_link(client: TestClient) -> None:
    sign_up(client)
    client.post("/v1/auth/password-reset/request", json={"email": "riley@example.com"})
    token = reset_token(client)
    weak = client.post(
        "/v1/auth/password-reset/confirm", json={"token": token, "new_password": "short"}
    )
    assert weak.status_code == 422
    good = client.post(
        "/v1/auth/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert good.status_code == 200


def test_reset_emails_are_limited_per_address(make_client: Callable[..., TestClient]) -> None:
    client = make_client(
        email_provider="outbox", app_base_url="http://localhost:5173", reset_emails_per_hour=2
    )
    sign_up(client)
    for _ in range(2):
        assert (
            client.post(
                "/v1/auth/password-reset/request", json={"email": "riley@example.com"}
            ).status_code
            == 202
        )
    limited = client.post("/v1/auth/password-reset/request", json={"email": "riley@example.com"})
    assert limited.status_code == 429
    assert len(outbox(client).outbox) == 2


def test_reset_confirm_rejects_malformed_tokens(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/password-reset/confirm", json={"token": "abc", "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 422


# --- Google and password on the same email ---


def test_google_takes_over_an_unverified_password_account(client: TestClient) -> None:
    # Someone registers another person's address with a password they chose...
    squatter = sign_up(client, email="jo@example.com").json()
    # ...then the real owner signs in with Google, which proves the address is theirs.
    google = client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"})
    assert google.status_code == 200
    assert google.json()["user"]["id"] == squatter["user"]["id"]
    assert google.json()["user"]["has_password"] is False
    assert client.get("/v1/auth/me", headers=bearer(squatter["access_token"])).status_code == 401
    assert log_in(client, email="jo@example.com").status_code == 401


def test_google_links_to_a_verified_password_account_and_keeps_its_password(
    client: TestClient,
) -> None:
    sign_up(client, email="jo@example.com")
    client.post("/v1/auth/password-reset/request", json={"email": "jo@example.com"})
    client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": reset_token(client), "new_password": NEW_PASSWORD},
    )
    google = client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"})
    assert google.json()["user"]["has_password"] is True
    assert log_in(client, email="jo@example.com", password=NEW_PASSWORD).status_code == 200


def test_password_sign_up_cannot_claim_a_google_account(client: TestClient) -> None:
    client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"})
    assert sign_up(client, email="jo@example.com").status_code == 409
    assert log_in(client, email="jo@example.com").status_code == 401


def test_google_account_can_add_a_password_through_reset(client: TestClient) -> None:
    client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"})
    client.post("/v1/auth/password-reset/request", json={"email": "jo@example.com"})
    client.post(
        "/v1/auth/password-reset/confirm",
        json={"token": reset_token(client), "new_password": NEW_PASSWORD},
    )
    assert log_in(client, email="jo@example.com", password=NEW_PASSWORD).status_code == 200
