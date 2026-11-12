"""Retention: old rows go, recent rows stay."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select

from mnemos_broker.db import create_session_factory
from mnemos_broker.models import AuditEvent, AuthChallenge, ReadRequest, VaultItem
from mnemos_broker.retention import Retention, RetentionPolicy

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


async def _seed(engine, *, old: datetime) -> None:
    factory = create_session_factory(engine)
    async with factory() as session:
        await session.execute(
            insert(VaultItem).values(
                id=uuid.uuid4(),
                owner="owner.testnet",
                scope="travel",
                ciphertext=b"x" * 32,
                nonce=b"n" * 12,
                wrapped_dek_owner=b"o" * 60,
                wrapped_dek_broker=b"b" * 92,
                content_hash="a" * 64,
                created_at=old,
                deleted_at=old,
            )
        )
        await session.execute(
            insert(AuthChallenge).values(
                nonce="b" * 64,
                account="owner.testnet",
                message="m",
                expires_at=old,
                created_at=old,
            )
        )
        await session.execute(
            insert(AuditEvent).values(owner="owner.testnet", kind="auth_ok", created_at=old)
        )
        await session.execute(
            insert(ReadRequest).values(
                req_id=999,
                owner="owner.testnet",
                agent="agent.testnet",
                scope="travel",
                q_hash="c" * 64,
                price=1,
                status="served",
                created_at=old,
            )
        )
        await session.commit()


async def _count(engine, table) -> int:
    factory = create_session_factory(engine)
    async with factory() as session:
        result = await session.execute(select(table))
        return len(list(result.all()))


@pytest.mark.asyncio
async def test_retention_removes_old_rows_and_keeps_recent_ones(clean_db) -> None:
    policy = RetentionPolicy(
        challenge_ttl=timedelta(hours=1),
        audit_age=timedelta(days=30),
        vault_age=timedelta(days=30),
        request_age=timedelta(days=90),
    )
    old = NOW - timedelta(days=400)
    await _seed(clean_db, old=old)

    retention = Retention(create_session_factory(clean_db), policy=policy)
    removed = await retention.run_once(now=NOW)

    assert removed["auth_challenges"] == 1
    assert removed["audit_events"] == 1
    assert removed["vault_items"] == 1
    assert removed["read_requests"] == 1

    assert await _count(clean_db, AuthChallenge) == 0
    assert await _count(clean_db, AuditEvent) == 0
    assert await _count(clean_db, VaultItem) == 0
    assert await _count(clean_db, ReadRequest) == 0


@pytest.mark.asyncio
async def test_retention_keeps_rows_inside_the_window(clean_db) -> None:
    recent = NOW - timedelta(minutes=5)
    await _seed(clean_db, old=recent)

    retention = Retention(
        create_session_factory(clean_db),
        policy=RetentionPolicy(
            challenge_ttl=timedelta(hours=1),
            audit_age=timedelta(days=30),
            vault_age=timedelta(days=30),
            request_age=timedelta(days=90),
        ),
    )
    removed = await retention.run_once(now=NOW)

    assert removed == {
        "auth_challenges": 0,
        "audit_events": 0,
        "vault_items": 0,
        "read_requests": 0,
    }
    assert await _count(clean_db, AuthChallenge) == 1
    assert await _count(clean_db, VaultItem) == 1
