"""Callback requests (/v1/support/callback-requests), security headers, and route gating."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.repositories.callbacks import InMemoryCallbackRepository
from tests.api.test_auth_api import bearer, google_client, sign_in

URL = "/v1/support/callback-requests"


def payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Jordan Lee",
        "contactMethod": "email",
        "contact": "Jordan@Example.com",
        "bestTime": "morning",
        "topic": "I'd like help choosing between term and permanent coverage.",
        "summary": {
            "estimate": {
                "total": 900000,
                "existing": 100000,
                "gap": 800000,
                "suggested": 800000,
                "termYears": 20,
            },
            "recentQuestions": ["How long should my term be?"],
        },
    }
    body.update(overrides)
    return body


def stored(client: TestClient) -> InMemoryCallbackRepository:
    repo = client.app.state.container.support._repo  # type: ignore[attr-defined]
    if not isinstance(repo, InMemoryCallbackRepository):
        pytest.skip("inspects the in-memory store; the Postgres run checks the API only")
    return repo


def test_callback_request_is_stored(client: TestClient) -> None:
    response = client.post(URL, json=payload())
    assert response.status_code == 201, response.text
    callback_id = response.json()["id"]
    assert callback_id.startswith("cbk_")

    [record] = stored(client).records
    assert record.id == callback_id
    assert record.contact == "jordan@example.com"
    assert record.user_id is None
    assert record.summary is not None and record.summary["estimate"]["termYears"] == 20


def test_phone_callback_without_summary(client: TestClient) -> None:
    body = payload(contactMethod="phone", contact="(555) 123-4567", summary=None)
    assert client.post(URL, json=body).status_code == 201


def test_signed_in_request_is_linked_to_the_account(
    make_client: Callable[..., TestClient],
) -> None:
    client = google_client(make_client)
    token = sign_in(client)["access_token"]
    assert client.post(URL, json=payload(), headers=bearer(token)).status_code == 201
    assert stored(client).records[0].user_id is not None


def test_bad_token_does_not_block_the_request(client: TestClient) -> None:
    response = client.post(URL, json=payload(), headers=bearer("not-a-real-token"))
    assert response.status_code == 201
    assert stored(client).records[0].user_id is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"topic": "My SSN is 123-45-6789"},
        {"topic": "Policy 1234567890123 needs review"},
        {"name": "Jordan 123 45 6789"},
        {"contact": "not-an-email"},
        {"contactMethod": "phone", "contact": "555-1234"},
        {"contactMethod": "phone", "contact": "call me at 5551234567"},
        {"bestTime": "midnight"},
        {"name": "   "},
        {"topic": "x" * 1001},
        {"extra": "field"},
        {
            "summary": {
                "estimate": {"total": 1, "existing": 0, "gap": 1, "suggested": 1, "termYears": 1},
                "recentQuestions": ["My card is 4111 1111 1111 1111"],
            }
        },
    ],
)
def test_invalid_or_sensitive_requests_are_rejected(
    client: TestClient, overrides: dict[str, Any]
) -> None:
    response = client.post(URL, json=payload(**overrides))
    assert response.status_code == 422, response.text
    # Validation errors never echo the submitted values back.
    assert "123-45-6789" not in response.text
    assert "4111" not in response.text


def test_callback_requests_are_rate_limited(make_client: Callable[..., TestClient]) -> None:
    client = make_client(support_rate_limit_per_hour=2)
    for _ in range(2):
        assert client.post(URL, json=payload()).status_code == 201
    limited = client.post(URL, json=payload())
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"


def test_security_headers_on_every_response(client: TestClient) -> None:
    for response in (client.get("/v1/health"), client.get("/v1/does-not-exist")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in response.headers["content-security-policy"]
        assert "strict-transport-security" not in response.headers


def test_deployed_service_hides_docs_and_sends_hsts(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(env="demo")
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert "max-age" in client.get("/v1/health").headers["strict-transport-security"]


def test_planner_api_is_off_unless_enabled(make_client: Callable[..., TestClient]) -> None:
    client = make_client(planner_api_enabled=False)
    assert client.post("/v1/sessions", json={}).status_code == 404
    assert client.get("/v1/content/coverage-types").status_code == 404
    assert client.get("/v1/health").status_code == 200
