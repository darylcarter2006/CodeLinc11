from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.ai.base import AIAdapter
from app.container import build_container
from app.main import create_app
from app.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    # Never read the developer's .env: tests must not touch a real (shared) database.
    # Explicit environment variables still apply, which is how CI selects Postgres.
    # Force ai_provider="stub" so tests never attempt real Bedrock calls.
    return Settings(env="test", cors_origins=["http://localhost:5173"], ai_provider="stub")


@pytest.fixture
def make_client(settings: Settings, clock: FakeClock) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(ai: AIAdapter | None = None, **overrides: Any) -> TestClient:
        effective = settings.model_copy(update=overrides)
        container = build_container(effective, ai=ai, clock=clock)
        client = TestClient(create_app(effective, container))
        # Entering the client keeps one event loop for all its requests, which pooled
        # database connections require.
        client.__enter__()
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


class SessionHandle:
    """Small helper so API tests read like the user flow."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        created = client.post("/v1/sessions", json={})
        assert created.status_code == 201, created.text
        body = created.json()
        self.id: str = body["session_id"]
        self.token: str = body["access_token"]
        self.revision: int = body["revision"]

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def url(self, suffix: str = "") -> str:
        return f"/v1/sessions/{self.id}{suffix}"

    def say(self, text: str, **extra: Any) -> Any:
        body = {
            "text": text,
            "client_request_id": str(uuid.uuid4()),
            "expected_revision": self.revision,
            **extra,
        }
        response = self.client.post(self.url("/messages"), headers=self.headers, json=body)
        if response.status_code == 200:
            self.revision = response.json()["revision"]
        return response

    def patch(self, updates: dict[str, Any] | None = None, confirm: list[str] | None = None) -> Any:
        body = {
            "expected_revision": self.revision,
            "client_request_id": str(uuid.uuid4()),
            "updates": updates or {},
            "confirm": confirm or [],
        }
        response = self.client.patch(self.url("/profile"), headers=self.headers, json=body)
        if response.status_code == 200:
            self.revision = response.json()["revision"]
        return response


@pytest.fixture
def session(client: TestClient) -> SessionHandle:
    return SessionHandle(client)
