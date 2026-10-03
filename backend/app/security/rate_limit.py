"""In-process sliding-window rate limiter.

Per instance only: with several instances each enforces its own limit. Good enough to
stop one client running up model costs in a demo; use an edge limit (WAF) in production.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from app.errors import RateLimited

MAX_TRACKED_CLIENTS = 10_000


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str) -> None:
        """Record a request for ``key``; raise RateLimited if it is over the limit."""
        now = self._clock()
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= MAX_TRACKED_CLIENTS:
                self._evict(now)
            hits = self._hits[key] = deque()
        while hits and hits[0] <= now - self._window:
            hits.popleft()
        if len(hits) >= self._limit:
            raise RateLimited()
        hits.append(now)

    def _evict(self, now: float) -> None:
        cutoff = now - self._window
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= cutoff]:
            del self._hits[key]
        if len(self._hits) >= MAX_TRACKED_CLIENTS:
            self._hits.clear()  # under a flood, forget everyone rather than grow unbounded
