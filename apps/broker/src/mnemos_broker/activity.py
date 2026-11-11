"""In-process activity fan-out for the owner SSE stream.

This is intentionally single-instance, matching the rate limiter. A deployment
with multiple broker replicas needs a shared bus (for example Postgres
LISTEN/NOTIFY); docs/DECISIONS.md records the limitation.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

MAX_QUEUE = 128
MAX_SUBSCRIBERS_PER_OWNER = 16


class ActivityPublisher:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def publish(self, owner: str, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(owner, set())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # A slow browser tab must not block settlement or inference.
                continue

    @asynccontextmanager
    async def subscribe(self, owner: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUE)
        subscribers = self._subscribers.setdefault(owner, set())
        if len(subscribers) >= MAX_SUBSCRIBERS_PER_OWNER:
            raise RuntimeError("too many activity stream subscribers for this owner")
        subscribers.add(queue)
        try:
            yield queue
        finally:
            subscribers.discard(queue)
            if not subscribers:
                self._subscribers.pop(owner, None)

    def subscriber_count(self, owner: str) -> int:
        return len(self._subscribers.get(owner, set()))
