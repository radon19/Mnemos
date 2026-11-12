"""Retention: the broker's tables must not grow without bound.

Nothing here deletes evidence that a read depends on. The rules are:

* ``auth_challenges`` are single use and expire after five minutes. They are
  kept for an hour so a failed sign-in can be explained, then dropped.
* ``audit_events`` are an operational trail, kept for a month.
* ``vault_items`` that the owner deleted are kept for a month so a mistake can
  be undone by support, then removed for good.
* ``read_requests`` are kept for a quarter. The chain keeps the receipt ring,
  so the history of a read never disappears, only the broker's copy of the
  bookkeeping.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Delete

from .models import AuditEvent, AuthChallenge, ReadRequest, VaultItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPolicy:
    challenge_ttl: timedelta = timedelta(hours=1)
    audit_age: timedelta = timedelta(days=30)
    vault_age: timedelta = timedelta(days=30)
    request_age: timedelta = timedelta(days=90)


class Retention:
    """Removes rows that are past their useful life."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: int = 3600,
        policy: RetentionPolicy | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.policy = policy or RetentionPolicy()
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def run_once(self, now: datetime | None = None) -> dict[str, int]:
        moment = now or datetime.now(UTC)
        policy = self.policy
        removed: dict[str, int] = {}
        async with self.session_factory() as session:
            removed["auth_challenges"] = await _delete(
                session,
                delete(AuthChallenge).where(
                    AuthChallenge.expires_at < moment - policy.challenge_ttl
                ),
            )
            removed["audit_events"] = await _delete(
                session,
                delete(AuditEvent).where(AuditEvent.created_at < moment - policy.audit_age),
            )
            removed["vault_items"] = await _delete(
                session,
                delete(VaultItem).where(
                    VaultItem.deleted_at.is_not(None),
                    VaultItem.deleted_at < moment - policy.vault_age,
                ),
            )
            removed["read_requests"] = await _delete(
                session,
                delete(ReadRequest).where(ReadRequest.created_at < moment - policy.request_age),
            )

            await session.commit()
        if any(removed.values()):
            logger.info("retention removed rows", extra={"removed": removed})
        return removed

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("retention run failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue


async def _delete(session: AsyncSession, statement: Delete) -> int:
    """Runs a delete and reports how many rows went."""
    result = await session.execute(statement)
    return int(cast("CursorResult[Any]", result).rowcount or 0)
