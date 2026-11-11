from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from mnemos_broker.chain import ChainReceipt

from .helpers import authenticate, insert_read_request

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_activity_merges_broker_and_chain(client, owner_key, clean_db, fake_chain) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    await insert_read_request(
        clean_db,
        req_id=1,
        owner="owner.testnet",
        agent="agent.testnet",
        scope="health",
        q_hash="a" * 64,
        price=10,
        status="served",
        served_at=datetime.now(UTC),
        receipt_hash="b" * 64,
    )
    fake_chain.receipts["owner.testnet"] = [
        ChainReceipt(
            req_id=2,
            agent="agent.testnet",
            scope="health",
            price=10,
            receipt_hash="c" * 64,
            served_ns=time.time_ns(),
        )
    ]
    response = await client.get("/v1/activity")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["req_id"] for item in items] == [2, 1]
    assert items[0]["source"] == "chain"
    assert items[1]["source"] == "broker"


@pytest.mark.asyncio
async def test_activity_cursor(client, owner_key, clean_db) -> None:
    await authenticate(client, account="owner.testnet", key=owner_key)
    for req_id in (1, 2, 3):
        await insert_read_request(
            clean_db,
            req_id=req_id,
            owner="owner.testnet",
            agent="agent.testnet",
            scope="health",
            q_hash="a" * 64,
            price=10,
            status="served",
        )
    first = await client.get("/v1/activity", params={"limit": 2})
    assert [item["req_id"] for item in first.json()["items"]] == [3, 2]
    cursor = first.json()["next_cursor"]
    assert cursor == "2"
    second = await client.get("/v1/activity", params={"limit": 2, "cursor": cursor})
    assert [item["req_id"] for item in second.json()["items"]] == [1]
    assert second.json()["next_cursor"] is None


@pytest.mark.asyncio
async def test_activity_requires_session(client) -> None:
    response = await client.get("/v1/activity")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_activity_survives_chain_outage(client, owner_key, fake_chain) -> None:
    from mnemos_broker.chain import ContractError

    await authenticate(client, account="owner.testnet", key=owner_key)
    fake_chain.failures["recent_receipts"] = ContractError("E_INTERNAL", "rpc failed")
    response = await client.get("/v1/activity")
    assert response.status_code == 200
    assert response.json()["items"] == []
