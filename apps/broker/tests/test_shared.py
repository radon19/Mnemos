"""The shared limiter and the shared activity bus.

These are the two pieces that make a second broker replica behave like one
deployment: one rate budget, one activity stream.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from mnemos_broker.activity import ActivityPublisher
from mnemos_broker.activity_bus import ActivityBus, asyncpg_dsn
from mnemos_broker.db import create_session_factory
from mnemos_broker.ratelimit import RateLimiter
from mnemos_broker.shared_limiter import SharedLimiter

pytestmark = pytest.mark.integration

WINDOW = timedelta(minutes=1)


@pytest.mark.asyncio
async def test_two_replicas_spend_one_budget(clean_db) -> None:
    factory = create_session_factory(clean_db)
    first = SharedLimiter(factory)
    second = SharedLimiter(factory)
    await first.ensure_table()

    assert (await first.hit("ask:agent", limit=2, window=WINDOW)).allowed
    assert (await second.hit("ask:agent", limit=2, window=WINDOW)).allowed
    decision = await first.hit("ask:agent", limit=2, window=WINDOW)
    assert decision.allowed is False
    assert await second.count_of("ask:agent", window=WINDOW) == 3


@pytest.mark.asyncio
async def test_the_limiter_uses_the_shared_budget(clean_db) -> None:
    factory = create_session_factory(clean_db)
    shared = SharedLimiter(factory)
    await shared.ensure_table()
    limiter = RateLimiter(shared=shared)

    assert await limiter.allow("auth:1.2.3.4", capacity=1, per_seconds=60)
    assert not await limiter.allow("auth:1.2.3.4", capacity=1, per_seconds=60)
    assert await limiter.allow("auth:5.6.7.8", capacity=1, per_seconds=60)


@pytest.mark.asyncio
async def test_the_limiter_fails_open_when_the_database_is_gone() -> None:
    class BrokenSessionFactory:
        def __call__(self):
            raise RuntimeError("the database is unreachable")

    limiter = RateLimiter(shared=SharedLimiter(BrokenSessionFactory()))  # type: ignore[arg-type]
    assert await limiter.allow("ask:agent", capacity=1, per_seconds=60)


@pytest.mark.asyncio
async def test_an_event_reaches_the_other_replica(clean_db) -> None:
    # The engine URL masks the password, so the real one comes from the
    # settings. The channel is per database, and both replicas use the same.
    from mnemos_broker.config import get_settings

    database_url = get_settings().database_url
    first_publisher = ActivityPublisher()
    second_publisher = ActivityPublisher()
    first = ActivityBus(first_publisher, database_url)
    second = ActivityBus(second_publisher, database_url)
    await first.start()
    await second.start()
    try:
        async with second_publisher.subscribe("owner.testnet") as queue:
            first.publish(
                "owner.testnet",
                {"type": "read_served", "req_id": 7, "owner": "owner.testnet"},
            )
            for _ in range(50):
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=0.2)
                except TimeoutError:
                    continue
                assert event["req_id"] == 7
                break
            else:
                raise AssertionError("the event did not reach the other replica")
    finally:
        await first.close()
        await second.close()


def test_the_dsn_is_rewritten_for_asyncpg() -> None:
    assert (
        asyncpg_dsn("postgresql+asyncpg://user:pass@host:5432/db")
        == "postgresql://user:pass@host:5432/db"
    )
    assert asyncpg_dsn("sqlite:///db") is None
