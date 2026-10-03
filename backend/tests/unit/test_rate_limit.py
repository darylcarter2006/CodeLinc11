from __future__ import annotations

import pytest

from app.errors import RateLimited
from app.security import rate_limit
from app.security.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limit_applies_per_client_and_resets_after_the_window() -> None:
    clock = Clock()
    limiter = RateLimiter(2, window_seconds=60, clock=clock)
    limiter.check("a")
    limiter.check("a")
    with pytest.raises(RateLimited):
        limiter.check("a")
    limiter.check("b")  # other clients are unaffected

    clock.now += 61
    limiter.check("a")


def test_tracked_clients_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "MAX_TRACKED_CLIENTS", 3)
    clock = Clock()
    limiter = RateLimiter(5, window_seconds=60, clock=clock)
    for key in "abc":
        limiter.check(key)
    clock.now += 61
    limiter.check("d")  # expired clients are evicted to make room
    assert set(limiter._hits) == {"d"}

    for key in "ef":
        limiter.check(key)
    limiter.check("g")  # all still active: forget everyone rather than grow
    assert set(limiter._hits) == {"g"}
