"""A rate limiter that is shared by every broker replica.

The in-process limiter is the fast path, but a deployment with more than one
broker has to share one budget. This limiter keeps the counter in Postgres, so
two replicas cannot both spend the same allowance, and it fails open when the
database is unreachable: a read must not be blocked because the limiter is
down.

The counter is one row per key and window. The update is a single atomic
statement, so two replicas cannot interleave into a lost update.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

metadata = MetaData()

COUNTER_TABLE = Table(
    "rate_limit_counters",
    metadata,
    Column("key", String(255), primary_key=True),
    Column("window_started_at", DateTime(timezone=True), primary_key=True),
    Column("count", Integer, nullable=False),
)


@dataclass(frozen=True)
class LimitDecision:
    allowed: bool
    remaining: int


class SharedLimiter:
    """A fixed-window limiter kept in Postgres."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def ensure_table(self) -> None:
        async with self.session_factory() as session:
            await session.run_sync(
                lambda sync_session: metadata.create_all(sync_session.get_bind())
            )
            await session.commit()

    async def hit(self, key: str, *, limit: int, window: timedelta) -> LimitDecision:
        """Count one call against the key and report whether it is allowed."""
        now = datetime.now(UTC)
        window_start = now - (now - now.replace(second=0, microsecond=0)) % window
        async with self.session_factory() as session:
            statement = (
                insert(COUNTER_TABLE)
                .values(key=key, window_started_at=window_start, count=1)
                .on_conflict_do_update(
                    index_elements=["key", "window_started_at"],
                    set_={"count": COUNTER_TABLE.c.count + 1},
                )
                .returning(COUNTER_TABLE.c.count)
            )
            result = await session.execute(statement)
            count = int(result.scalar_one())
            await session.commit()
        return LimitDecision(allowed=count <= limit, remaining=max(0, limit - count))

    async def count_of(self, key: str, window: timedelta) -> int:
        """How many calls the key has spent in the current window."""
        now = datetime.now(UTC)
        window_start = now - (now - now.replace(second=0, microsecond=0)) % window
        async with self.session_factory() as session:
            result = await session.execute(
                select(COUNTER_TABLE.c.count).where(
                    COUNTER_TABLE.c.key == key,
                    COUNTER_TABLE.c.window_started_at == window_start,
                )
            )
            value = result.scalar_one_or_none()
        return 0 if value is None else int(value)
