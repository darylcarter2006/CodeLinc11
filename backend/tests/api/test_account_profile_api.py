"""Saved state per account: /v1/account/profile."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from fastapi.testclient import TestClient

URL = "/v1/account/profile"

STATE: dict[str, Any] = {
    "saved": {
        "p": {
            "deps": ["partner", "kids"],
            "children": 2,
            "youngest": 3,
            "age": 34,
            "income": 78000,
            "years": 19,
            "mortgage": 240000,
            "mortgageYears": 26,
            "otherDebt": 18000,
            "college": "public",
            "group": 156000,
            "policies": 0,
            "savings": 20000,
            "coverFor": "period",
            "budget": "lowest",
            "cashValue": "no",
            "legacy": "no",
            "simple": "yes",
        },
        "known": ["deps", "children", "income"],
        "confirmed": True,
        "updated": 1791093168684,
    },
    "log": [{"at": 1791093168684, "text": "Created your profile in the onboarding chat"}],
    "steps": {"Check the beneficiaries on your existing coverage": True},
    "policySeen": "term",
}


def account(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/v1/auth/signup", json={"name": "Riley", "email": email, "password": "correct horse 1"}
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_profile_needs_a_signed_in_account(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.put(URL, json=STATE).status_code == 401
    assert client.get(URL, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_new_account_has_no_saved_state(client: TestClient) -> None:
    assert client.get(URL, headers=account(client, "a@example.com")).json() == {
        "state": None,
        "updated_at": None,
    }


def test_saved_state_round_trips(client: TestClient) -> None:
    headers = account(client, "a@example.com")
    saved = client.put(URL, json=STATE, headers=headers)
    assert saved.status_code == 200, saved.text
    loaded = client.get(URL, headers=headers).json()
    assert loaded["state"] == STATE
    assert loaded["updated_at"] is not None


def test_each_account_sees_only_its_own_state(client: TestClient) -> None:
    first = account(client, "a@example.com")
    second = account(client, "b@example.com")
    client.put(URL, json=STATE, headers=first)
    assert client.get(URL, headers=second).json()["state"] is None


def test_state_follows_the_account_to_a_new_sign_in(client: TestClient) -> None:
    client.put(URL, json=STATE, headers=account(client, "a@example.com"))
    login = client.post(
        "/v1/auth/login", json={"email": "a@example.com", "password": "correct horse 1"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(URL, headers=headers).json()["state"] == STATE


def _with(path: list[str | int], value: Any) -> dict[str, Any]:
    state = copy.deepcopy(STATE)
    target: Any = state
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return state


@pytest.mark.parametrize(
    "state",
    [
        _with(["saved", "p", "income"], -1),
        _with(["saved", "p", "college"], "ivy"),
        _with(["saved", "known"], ["income", "not_a_field"]),
        _with(["saved", "extra"], 1),
        _with(["policySeen"], "whole"),
        _with(["log"], [{"at": 1, "text": "x"}] * 51),
        _with(["log"], [{"at": 1, "text": "x" * 301}]),
        _with(["steps"], {f"step {i}": True for i in range(21)}),
        _with(["unexpected"], True),
    ],
)
def test_invalid_state_is_rejected(client: TestClient, state: dict[str, Any]) -> None:
    headers = account(client, "a@example.com")
    assert client.put(URL, json=state, headers=headers).status_code == 422
    assert client.get(URL, headers=headers).json()["state"] is None


def test_oversized_state_is_rejected(client: TestClient) -> None:
    headers = account(client, "a@example.com")
    huge = _with(["steps"], {"x" * 300: True, "y" * 300: False})
    huge["padding"] = "z" * 20_000
    assert client.put(URL, json=huge, headers=headers).status_code == 413
