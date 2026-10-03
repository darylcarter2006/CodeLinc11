"""Google sign-in: /v1/auth/google, /v1/auth/me, /v1/auth/logout."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from tests.conftest import FakeClock
from tests.fakes import FakeGoogleVerifier

CLIENT_ID = "123456789-abc.apps.googleusercontent.com"
GOOD = "good:google-sub-1:jordan@example.com"


def google_client(make_client: Callable[..., TestClient], **overrides: object) -> TestClient:
    return make_client(
        google_verifier=FakeGoogleVerifier(), google_client_id=CLIENT_ID, **overrides
    )


def sign_in(client: TestClient, credential: str = GOOD) -> dict[str, object]:
    response = client.post("/v1/auth/google", json={"credential": credential})
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


def bearer(token: object) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_sign_in_is_off_without_a_client_id(client: TestClient) -> None:
    response = client.post("/v1/auth/google", json={"credential": GOOD + "-padding"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_unavailable"


def test_sign_in_returns_token_and_user(make_client: Callable[..., TestClient]) -> None:
    body = sign_in(google_client(make_client))
    assert isinstance(body["access_token"], str) and len(body["access_token"]) == 64
    user = body["user"]
    assert isinstance(user, dict)
    assert user == {
        "id": user["id"],
        "email": "jordan@example.com",
        "name": "Jordan Lee",
        "given_name": "Jordan",
        "picture": None,
    }
    assert str(user["id"]).startswith("usr_")


def test_me_returns_the_signed_in_user(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client)
    body = sign_in(client)
    me = client.get("/v1/auth/me", headers=bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == "jordan@example.com"


def test_same_google_account_maps_to_same_user(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client)
    first = sign_in(client)
    second = sign_in(client)
    assert first["user"] == second["user"]
    assert first["access_token"] != second["access_token"]


def test_different_google_accounts_are_different_users(
    make_client: Callable[..., TestClient],
) -> None:
    client = google_client(make_client)
    a = sign_in(client, "good:sub-a:a@example.com")
    b = sign_in(client, "good:sub-b:b@example.com")
    assert a["user"]["id"] != b["user"]["id"]  # type: ignore[index]


def test_invalid_credential_is_rejected(make_client: Callable[..., TestClient]) -> None:
    response = google_client(make_client).post(
        "/v1/auth/google", json={"credential": "forged-token-from-somewhere"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credential"


def test_google_unreachable_is_503(make_client: Callable[..., TestClient]) -> None:
    client = make_client(
        google_verifier=FakeGoogleVerifier(unreachable=True), google_client_id=CLIENT_ID
    )
    response = client.post("/v1/auth/google", json={"credential": GOOD})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "auth_provider_unreachable"


def test_me_requires_a_valid_token(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client)
    assert client.get("/v1/auth/me").status_code == 401
    assert client.get("/v1/auth/me", headers=bearer("nope")).status_code == 401


def test_anonymous_session_token_is_not_an_account_token(
    make_client: Callable[..., TestClient],
) -> None:
    client = google_client(make_client)
    session_token = client.post("/v1/sessions").json()["access_token"]
    assert client.get("/v1/auth/me", headers=bearer(session_token)).status_code == 401


def test_logout_revokes_the_token(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client)
    token = sign_in(client)["access_token"]
    assert client.post("/v1/auth/logout", headers=bearer(token)).status_code == 204
    assert client.get("/v1/auth/me", headers=bearer(token)).status_code == 401


def test_token_expires(make_client: Callable[..., TestClient], clock: FakeClock) -> None:
    client = google_client(make_client, account_token_ttl_hours=1)
    token = sign_in(client)["access_token"]
    clock.advance(hours=2)
    response = client.get("/v1/auth/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_sign_in_is_rate_limited(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client, auth_rate_limit_per_minute=2)
    sign_in(client)
    sign_in(client)
    response = client.post("/v1/auth/google", json={"credential": GOOD})
    assert response.status_code == 429


def test_rejects_malformed_requests(make_client: Callable[..., TestClient]) -> None:
    client = google_client(make_client)
    assert client.post("/v1/auth/google", json={}).status_code == 422
    assert client.post("/v1/auth/google", json={"credential": "short"}).status_code == 422
    extra = {"credential": GOOD, "email": "admin@example.com"}
    assert client.post("/v1/auth/google", json=extra).status_code == 422
