"""Rate limiting, with a shared budget when there is more than one replica.

The in-process token bucket is the default: it is fast and it is correct for
the single-broker deployment that ships here. A deployment with several
brokers can switch the shared backend on, and every replica then spends from
one budget kept in Postgres.

The shared backend fails open. A read must not be blocked because the limiter
could not reach the database.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from .shared_limiter import SharedLimiter

logger = logging.getLogger(__name__)


@dataclass
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """A token bucket, optionally backed by a shared counter."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        shared: SharedLimiter | None = None,
    ) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._calls = 0
        self._clock = clock or time.monotonic
        self._shared = shared

    async def allow(self, key: str, *, capacity: int, per_seconds: float = 60.0) -> bool:
        if self._shared is not None:
            return await self._allow_shared(key, capacity=capacity, per_seconds=per_seconds)
        return self._allow_local(key, capacity=capacity, per_seconds=per_seconds)

    async def _allow_shared(self, key: str, *, capacity: int, per_seconds: float) -> bool:
        assert self._shared is not None
        try:
            decision = await self._shared.hit(
                key, limit=capacity, window=timedelta(seconds=per_seconds)
            )
        except Exception:
            logger.warning("the shared limiter is unreachable; failing open", exc_info=True)
            return True
        return decision.allowed

    def _allow_local(self, key: str, *, capacity: int, per_seconds: float) -> bool:
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
