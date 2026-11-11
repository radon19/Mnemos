"""In-process token bucket.

Single-instance only: each broker replica has its own buckets. This is recorded
in docs/DECISIONS.md; a multi-replica deployment must move the limiter to
Postgres or a shared cache.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._calls = 0
        self._clock = clock or time.monotonic

    def allow(self, key: str, *, capacity: int, per_seconds: float = 60.0) -> bool:
        now = self._clock()
        bucket = self._buckets.get(key)
        refill = capacity / per_seconds
        if bucket is None:
            bucket = _Bucket(tokens=float(capacity), updated=now)
        else:
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(float(capacity), bucket.tokens + elapsed * refill)
            bucket.updated = now
        if bucket.tokens < 1.0:
            self._buckets[key] = bucket
            return False
        bucket.tokens -= 1.0
        self._buckets[key] = bucket
        self._calls += 1
        if self._calls % 1000 == 0:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        stale = [key for key, bucket in self._buckets.items() if now - bucket.updated > 3600]
        for key in stale:
            self._buckets.pop(key, None)

    def reset(self) -> None:
        self._buckets.clear()
        self._calls = 0
