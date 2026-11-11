"""Background expiry sweeper.

It can only expire requests the broker has seen and claimed in ``read_requests``.
A request created on chain and never sent to ``/v1/ask`` is invisible to this
service; the agent that created it should call ``expire_request`` itself. The
limitation is documented instead of pretending the sweeper can enumerate chain
state without an indexer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .activity import ActivityPublisher
from .chain import ChainProtocol, ContractError
from .models import ReadRequest

logger = logging.getLogger(__name__)

SWEEPABLE_STATUSES = ("processing", "refund_failed")


class Sweeper:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        chain: ChainProtocol,
        publisher: ActivityPublisher,
        interval_seconds: int = 60,
        ttl_seconds: int = 600,
    ) -> None:
        self.session_factory = session_factory
        self.chain = chain
        self.publisher = publisher
        self.interval_seconds = interval_seconds
        self.ttl = timedelta(seconds=ttl_seconds)
        self._stopped = asyncio.Event()

    async def run_forever(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("sweeper iteration failed")
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self.interval_seconds)
            except TimeoutError:
                continue

    def stop(self) -> None:
        self._stopped.set()

    async def run_once(self) -> int:
        cutoff = datetime.now(UTC) - self.ttl
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(ReadRequest)
                    .where(
                        ReadRequest.status.in_(SWEEPABLE_STATUSES),
                        ReadRequest.created_at < cutoff,
                    )
                    .order_by(ReadRequest.created_at)
                    .limit(50)
                )
            ).all()
        expired = 0
        for row in rows:
            try:
                await self.chain.expire_request(row.req_id)
            except ContractError as error:
                if error.code in {"E_REQUEST_NOT_FOUND", "E_REQUEST_NOT_APPROVED"}:
                    await self._mark(row.req_id, "expired")
                    expired += 1
                    continue
                if error.code == "E_REQUEST_NOT_EXPIRED":
                    continue
                logger.warning(
                    "sweeper could not expire request",
                    extra={"req_id": row.req_id, "error_code": error.code},
                )
                continue
            await self._mark(row.req_id, "expired")
            self.publisher.publish(
                row.owner,
                {
                    "type": "request_expired",
                    "req_id": row.req_id,
                    "agent": row.agent,
                    "scope": row.scope,
                    "at": datetime.now(UTC).isoformat(timespec="seconds"),
                },
            )
            expired += 1
        return expired

    async def _mark(self, req_id: int, status: str) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(ReadRequest)
                .where(ReadRequest.req_id == req_id)
                .values(status=status, error_code="E_REQUEST_EXPIRED")
            )
            await session.commit()
