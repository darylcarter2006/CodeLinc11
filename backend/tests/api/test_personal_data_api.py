"""Deleting an account on request, deleting old data on schedule, and crash logs without values."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.logging_config import JsonFormatter
from app.repositories.callbacks import InMemoryCallbackRepository
from tests.conftest import FakeClock
from tests.fakes import FakeGoogleVerifier

PASSWORD = "correct horse battery"
CALLBACK = {
    "name": "Riley",
    "contactMethod": "email",
    "contact": "riley@example.com",
    "bestTime": "any",
    "topic": "Help with term length",
}


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client(
        google_verifier=FakeGoogleVerifier(),
        google_client_id="123456789-abc.apps.googleusercontent.com",
        auth_rate_limit_per_minute=1000,
    )


def sign_up(client: TestClient, email: str = "riley@example.com") -> dict[str, str]:
    body = {"name": "Riley", "email": email, "password": PASSWORD}
    token = client.post("/v1/auth/signup", json=body).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def delete(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    return client.request("DELETE", "/v1/account", json=body, headers=headers)


def callbacks(client: TestClient) -> InMemoryCallbackRepository:
    repo = client.app.state.container.support._repo  # type: ignore[attr-defined]
    if not isinstance(repo, InMemoryCallbackRepository):
        pytest.skip("inspects the in-memory store")
    return repo


def test_deleting_an_account_needs_its_password(client: TestClient) -> None:
    headers = sign_up(client)
    wrong = delete(client, headers, password="not my password")
    assert wrong.status_code == 401
    assert delete(client, headers).status_code == 401
    assert client.get("/v1/auth/me", headers=headers).status_code == 200


def test_deleting_an_account_removes_everything_kept_for_it(client: TestClient) -> None:
    headers = sign_up(client)
    client.put(
        "/v1/account/profile",
        json={"saved": {"p": {"income": 78000}, "known": ["income"]}},
        headers=headers,
    )
    client.post("/v1/support/callback-requests", json=CALLBACK, headers=headers)

    assert delete(client, headers, password=PASSWORD).status_code == 204
    assert client.get("/v1/auth/me", headers=headers).status_code == 401
    login = {"email": "riley@example.com", "password": PASSWORD}
    assert client.post("/v1/auth/login", json=login).status_code == 401
    assert callbacks(client).records == []
    # The address is free again, with nothing carried over.
    again = sign_up(client)
    assert client.get("/v1/account/profile", headers=again).json()["state"] is None


def test_google_only_account_deletes_without_a_password(client: TestClient) -> None:
    token = client.post("/v1/auth/google", json={"credential": "good:sub-1:jo@example.com"}).json()[
        "access_token"
    ]
    assert delete(client, {"Authorization": f"Bearer {token}"}).status_code == 204


def test_deleting_needs_a_signed_in_account(client: TestClient) -> None:
    assert delete(client, {}).status_code == 401


def test_sweep_deletes_unused_accounts_and_old_callback_requests(
    client: TestClient, clock: FakeClock
) -> None:
    container = client.app.state.container  # type: ignore[attr-defined]
    old = sign_up(client, "old@example.com")
    client.post("/v1/support/callback-requests", json=CALLBACK)
    clock.advance(days=100)
    sign_up(client, "recent@example.com")
    clock.advance(days=81)  # old: 181 days unused; recent: 81 days

    # Run on the client's own event loop, as the server's background task would.
    accounts, requests = client.portal.call(container.personal_data.sweep)  # type: ignore[union-attr]
    assert (accounts, requests) == (1, 1)
    assert client.get("/v1/auth/me", headers=old).status_code == 401
    login = {"email": "recent@example.com", "password": PASSWORD}
    assert client.post("/v1/auth/login", json=login).status_code == 200
    assert callbacks(client).records == []


def test_crash_logs_keep_the_stack_but_not_the_message() -> None:
    income, email = 78000, "riley@example.com"
    try:
        raise ValueError(f"income {income} for {email}")
    except ValueError:
        record = logging.LogRecord("app", logging.ERROR, __file__, 1, "unhandled_error", (), None)
        record.exc_info = sys.exc_info()
    line = JsonFormatter().format(record)
    assert "ValueError" in line
    assert "test_crash_logs_keep_the_stack_but_not_the_message" in line
    assert "78000" not in line and "riley@example.com" not in line
