from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import FakeClock, SessionHandle


def test_create_session_returns_token_and_expiry(client: TestClient) -> None:
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "revision", "access_token", "expires_at"}
    assert body["revision"] == 0
    assert len(body["access_token"]) == 64


def test_create_session_accepts_empty_body(client: TestClient) -> None:
    assert client.post("/v1/sessions").status_code == 201


def test_new_session_starts_with_first_question(session: SessionHandle) -> None:
    body = session.client.get(session.url(), headers=session.headers).json()
    assert body["next_question"]["field"] == "dependents_count"
    assert body["assessment"]["status"] == "incomplete"
    assert body["turn_count"] == 0
    assert body["turn_limit"] == 40


def test_token_is_required(session: SessionHandle) -> None:
    response = session.client.get(session.url())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_invalid_token_is_rejected(session: SessionHandle) -> None:
    response = session.client.get(session.url(), headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_token_for_another_session_looks_like_not_found(client: TestClient) -> None:
    a, b = SessionHandle(client), SessionHandle(client)
    response = client.get(b.url(), headers=a.headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_session_id_alone_is_not_authorization(session: SessionHandle) -> None:
    headers = {"Authorization": f"Bearer {session.id}"}
    assert session.client.get(session.url(), headers=headers).status_code == 401


def test_expired_session(session: SessionHandle, clock: FakeClock) -> None:
    clock.advance(hours=5)
    response = session.client.get(session.url(), headers=session.headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_refresh_token_replaces_old_token_and_extends_session(
    session: SessionHandle, clock: FakeClock
) -> None:
    clock.advance(hours=3)
    response = session.client.post(session.url("/token"), headers=session.headers)
    assert response.status_code == 200
    new_token = response.json()["access_token"]

    old = session.client.get(session.url(), headers=session.headers)
    assert old.status_code == 401

    clock.advance(hours=3)  # past the original 4h expiry
    fresh = session.client.get(session.url(), headers={"Authorization": f"Bearer {new_token}"})
    assert fresh.status_code == 200


def test_delete_removes_session_and_tokens(session: SessionHandle) -> None:
    session.say("2")
    assert session.client.delete(session.url(), headers=session.headers).status_code == 204
    assert session.client.get(session.url(), headers=session.headers).status_code == 401
    assert session.client.get(session.url("/messages"), headers=session.headers).status_code == 401


def test_health_and_ready(client: TestClient) -> None:
    assert client.get("/v1/health").json() == {"status": "ok"}
    assert client.get("/v1/ready").json() == {"status": "ok"}
