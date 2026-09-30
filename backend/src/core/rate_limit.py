"""Per-user rate limiting for expensive AI operations (cost-abuse protection).

A small sliding-window limiter keyed by (user_id, operation). The default
implementation is in-memory (single process); the ``RateLimiter`` protocol lets
it be swapped for a shared store (DynamoDB/Redis) when running multiple tasks,
without changing call sites. See security.md ("Cost-abuse protection").
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Protocol


class RateLimiter(Protocol):
    def check(self, user_id: str, operation: str) -> bool:
        """Return True if the call is allowed, False if the limit is exceeded."""
        ...


class InMemoryRateLimiter:
    """Sliding-window limiter: at most ``limit`` calls per ``window_seconds``.

    Suitable for local/dev and single-task deployments. For multi-task ECS,
    back this with a shared store (the protocol keeps call sites unchanged).
    """

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self._limit = limit
        self._window = window_seconds
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def check(self, user_id: str, operation: str) -> bool:
        now = time.monotonic()
        key = (user_id, operation)
        events = self._events[key]
        cutoff = now - self._window
        while events and events[0] < cutoff:
            events.popleft()
        if len(events) >= self._limit:
            return False
        events.append(now)
        return True
