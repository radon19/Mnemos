from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mnemos_broker.activity import ActivityPublisher
from mnemos_broker.chain import ContractError
from mnemos_broker.db import create_session_factory
from mnemos_broker.models import ReadRequest
from mnemos_broker.sweeper import Sweeper

from .helpers import insert_read_request

pytestmark = pytest.mark.integration


def build_sweeper(engine, chain, publisher) -> Sweeper:
    return Sweeper(
        session_factory=create_session_factory(engine),
        chain=chain,
        publisher=publisher,
        interval_seconds=60,
        ttl_seconds=600,
    )


async def row(engine, req_id: int) -> ReadRequest | None:
    async with create_session_factory(engine)() as session:
        return await session.get(ReadRequest, req_id)


@pytest.mark.asyncio
async def test_stale_processing_request_is_expired(clean_db, fake_chain) -> None:
    insert = datetime.now(UTC) - timedelta(minutes=20)
    await insert_read_request(
        clean_db,
        req_id=1,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="processing",
        created_at=insert,
    )
    publisher = ActivityPublisher()
    sweeper = build_sweeper(clean_db, fake_chain, publisher)
    expired = await sweeper.run_once()
    assert expired == 1
    assert fake_chain.expired == [1]
    stored = await row(clean_db, 1)
    assert stored is not None
    assert stored.status == "expired"
    assert stored.error_code == "E_REQUEST_EXPIRED"


@pytest.mark.asyncio
async def test_fresh_request_is_not_touched(clean_db, fake_chain) -> None:
    await insert_read_request(
        clean_db,
        req_id=2,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="processing",
    )
    sweeper = build_sweeper(clean_db, fake_chain, ActivityPublisher())
    assert await sweeper.run_once() == 0
    assert fake_chain.expired == []
    stored = await row(clean_db, 2)
    assert stored is not None and stored.status == "processing"


@pytest.mark.asyncio
async def test_already_settled_request_is_marked_expired(clean_db, fake_chain) -> None:
    insert = datetime.now(UTC) - timedelta(minutes=20)
    await insert_read_request(
        clean_db,
        req_id=3,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="processing",
        created_at=insert,
    )
    fake_chain.failures["expire_request"] = ContractError(
        "E_REQUEST_NOT_FOUND", "request already settled"
    )
    sweeper = build_sweeper(clean_db, fake_chain, ActivityPublisher())
    assert await sweeper.run_once() == 1
    stored = await row(clean_db, 3)
    assert stored is not None and stored.status == "expired"


@pytest.mark.asyncio
async def test_not_yet_expired_on_chain_leaves_row_alone(clean_db, fake_chain) -> None:
    insert = datetime.now(UTC) - timedelta(minutes=20)
    await insert_read_request(
        clean_db,
        req_id=4,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="refund_failed",
        created_at=insert,
    )
    fake_chain.failures["expire_request"] = ContractError(
        "E_REQUEST_NOT_EXPIRED", "request has not reached its deadline"
    )
    sweeper = build_sweeper(clean_db, fake_chain, ActivityPublisher())
    assert await sweeper.run_once() == 0
    stored = await row(clean_db, 4)
    assert stored is not None and stored.status == "refund_failed"


@pytest.mark.asyncio
async def test_sweeper_publishes_event(clean_db, fake_chain) -> None:
    insert = datetime.now(UTC) - timedelta(minutes=20)
    await insert_read_request(
        clean_db,
        req_id=5,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="processing",
        created_at=insert,
    )
    publisher = ActivityPublisher()
    async with publisher.subscribe("owner.testnet") as queue:
        sweeper = build_sweeper(clean_db, fake_chain, publisher)
        await sweeper.run_once()
        event = queue.get_nowait()
    assert event["type"] == "request_expired"
    assert event["req_id"] == 5
