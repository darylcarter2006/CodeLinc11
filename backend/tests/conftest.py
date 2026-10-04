from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.ai.base import AIAdapter
from app.container import build_container
from app.main import create_app
from app.security.google import GoogleTokenVerifier
from app.settings import Settings


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(autouse=True)
def _empty_test_database() -> None:
    """With REPOSITORY_BACKEND=postgres, start every test from empty tables.

    Only ever against a database on this machine: the suite refuses to touch anything else.
    """
    if os.environ.get("REPOSITORY_BACKEND") != "postgres":
        return
    url = os.environ.get("DATABASE_URL", "")
    if urlparse(url).hostname not in ("localhost", "127.0.0.1"):
        pytest.exit("Postgres tests run only against a local database (DATABASE_URL host).")
    import asyncpg

    async def truncate() -> None:
        conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
            names = ", ".join(f'"{row["tablename"]}"' for row in tables)
            await conn.execute(f"TRUNCATE {names} CASCADE")
        finally:
            await conn.close()

    asyncio.run(truncate())


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    # Never read the developer's .env: tests must not touch a real (shared) database.
    # Explicit environment variables still apply, which is how CI selects Postgres.
    return Settings(
        _env_file=None,
        env="test",
        cors_origins=["http://localhost:5173"],
        planner_api_enabled=True,
    )


@pytest.fixture
def make_client(settings: Settings, clock: FakeClock) -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def factory(
        ai: AIAdapter | None = None,
        google_verifier: GoogleTokenVerifier | None = None,
        **overrides: Any,
    ) -> TestClient:
        effective = settings.model_copy(update=overrides)
        container = build_container(effective, ai=ai, google_verifier=google_verifier, clock=clock)
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
