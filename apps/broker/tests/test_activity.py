from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack

import pytest

from mnemos_broker.activity import MAX_QUEUE, MAX_SUBSCRIBERS_PER_OWNER, ActivityPublisher


@pytest.mark.asyncio
async def test_publish_reaches_subscriber() -> None:
    publisher = ActivityPublisher()
    async with publisher.subscribe("owner.testnet") as queue:
        publisher.publish("owner.testnet", {"type": "read_served", "req_id": 1})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"type": "read_served", "req_id": 1}
        assert publisher.subscriber_count("owner.testnet") == 1
    assert publisher.subscriber_count("owner.testnet") == 0


@pytest.mark.asyncio
async def test_other_owners_do_not_receive_events() -> None:
    publisher = ActivityPublisher()
    async with publisher.subscribe("owner.testnet") as queue:
        publisher.publish("someone-else.testnet", {"type": "read_served"})
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.05)
        assert queue.empty()


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_raise() -> None:
    publisher = ActivityPublisher()
    async with publisher.subscribe("owner.testnet") as queue:
        for index in range(MAX_QUEUE + 20):
            publisher.publish("owner.testnet", {"index": index})
        assert queue.qsize() == MAX_QUEUE


@pytest.mark.asyncio
async def test_subscriber_cap() -> None:
    publisher = ActivityPublisher()
    async with AsyncExitStack() as stack:
        for _ in range(MAX_SUBSCRIBERS_PER_OWNER):
            await stack.enter_async_context(publisher.subscribe("owner.testnet"))
        with pytest.raises(RuntimeError):
            await stack.enter_async_context(publisher.subscribe("owner.testnet"))
