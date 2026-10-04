from __future__ import annotations

import logging
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_request_id_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/v1/health")
    assert generated.headers["x-request-id"].startswith("req_")

    echoed = client.get("/v1/health", headers={"X-Request-ID": "trace-123"})
    assert echoed.headers["x-request-id"] == "trace-123"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/v1/health", headers={"X-Request-ID": "bad id with spaces"})
    assert response.headers["x-request-id"].startswith("req_")


def test_errors_use_envelope_with_request_id(client: TestClient) -> None:
    response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["x-request-id"]


def test_oversized_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/sessions",
        content=b"{" + b" " * 20_000 + b"}",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_unhandled_error_returns_500_envelope(make_client: Callable[..., TestClient]) -> None:
    client = make_client()
    app = client.app
    assert isinstance(app, FastAPI)

    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.add_api_route("/boom", boom)

    response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret" not in response.text
    assert body["error"]["request_id"] == response.headers["x-request-id"]


def test_cors_allows_configured_origin_only(client: TestClient) -> None:
    allowed = client.options(
        "/v1/sessions",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/v1/sessions",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_cors_allows_every_method_the_api_uses(client: TestClient) -> None:
    """The front end is on another domain, so the browser asks first (a preflight) before any
    request with a token or JSON. Every route's method must pass, or the browser blocks it."""
    paths = client.app.openapi()["paths"]  # type: ignore[attr-defined]
    routes = [(path, method.upper()) for path, ops in paths.items() for method in ops]
    assert ("/v1/account/profile", "PUT") in routes
    for path, method in routes:
        response = client.options(
            path,
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200, f"{method} {path}: {response.text}"


def test_validation_errors_do_not_echo_input(client: TestClient) -> None:
    response = client.post("/v1/sessions", json={"secret_field": "my ssn"})
    assert response.status_code == 422
    assert "my ssn" not in response.text


def test_access_log_never_contains_session_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    created = client.post("/v1/sessions").json()
    session_id = created["session_id"]
    with caplog.at_level(logging.INFO, logger="app.access"):
        client.get(
            f"/v1/sessions/{session_id}",
            headers={"Authorization": f"Bearer {created['access_token']}"},
        )
    endpoints = [r.__dict__["endpoint"] for r in caplog.records if r.name == "app.access"]
    assert endpoints[-1] == "/v1/sessions/{session_id}"
    app_logs = " ".join(str(r.__dict__) for r in caplog.records if r.name.startswith("app"))
    assert session_id not in app_logs
    assert created["access_token"] not in app_logs
