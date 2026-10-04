"""One container serving the whole app: the built front end from STATIC_DIR, plus the API."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def site(tmp_path: Path) -> Path:
    root = tmp_path / "web"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Coverage Compass</title>")
    (root / "assets" / "app-abc123.js").write_text("console.log('app')")
    (root / "favicon.ico").write_bytes(b"\x00\x00")
    (tmp_path / "secret.txt").write_text("not for the web")
    return root


@pytest.fixture
def client(make_client: Callable[..., TestClient], site: Path) -> TestClient:
    return make_client(static_dir=str(site))


def test_pages_get_the_app_and_its_security_policy(client: TestClient) -> None:
    for path in ("/", "/dashboard", "/reset-password"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Coverage Compass" in response.text
        assert "default-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["cache-control"] == "no-cache"


def test_built_files_are_served_and_cached(client: TestClient) -> None:
    response = client.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]
    assert client.get("/favicon.ico").status_code == 200


def test_api_paths_never_get_the_page(client: TestClient) -> None:
    missing = client.get("/v1/not-an-endpoint")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    health = client.get("/v1/health")
    assert health.json() == {"status": "ok"}
    assert health.headers["content-security-policy"].startswith("default-src 'none'")


def test_files_outside_the_site_are_not_served(client: TestClient) -> None:
    response = client.get("/..%2Fsecret.txt")
    assert "not for the web" not in response.text
