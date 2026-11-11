"""Owner activity: merged broker records and on-chain receipts, plus SSE."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..activity import MAX_SUBSCRIBERS_PER_OWNER
from ..chain import ContractError
from ..errors import E_RATE_LIMITED, MnemosError
from ..models import ReadRequest
from ..schemas import ActivityItem, ActivityPage
from ..security import SessionClaims
from .deps import get_db, get_services, require_owner

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activity", tags=["activity"])

CHAIN_RECEIPT_PAGE = 50
CHAIN_RECEIPT_PAGES = 4


def _chain_time(served_ns: int) -> datetime:
    return datetime.fromtimestamp(served_ns / 1_000_000_000, UTC)


def _from_record(row: ReadRequest) -> ActivityItem:
    return ActivityItem(
        req_id=row.req_id,
        agent=row.agent,
        scope=row.scope,
        price=str(row.price),
        status=row.status,
        source="broker",
        created_at=row.created_at,
        served_at=row.served_at,
        receipt_hash=row.receipt_hash,
        receipt_tx_hash=row.receipt_tx_hash,
        refund_tx_hash=row.refund_tx_hash,
        chat_id=row.chat_id,
        attestation=row.attestation,
        latency_ms=row.latency_ms,
        error_code=row.error_code,
    )


async def _chain_receipts(request: Request, owner: str) -> list[ActivityItem]:
    services = get_services(request)
    receipts: list[ActivityItem] = []
    try:
        for page in range(CHAIN_RECEIPT_PAGES):
            batch = await services.chain.recent_receipts(
                owner, page * CHAIN_RECEIPT_PAGE, CHAIN_RECEIPT_PAGE
            )
            for receipt in batch:
                served_at = _chain_time(receipt.served_ns)
                receipts.append(
                    ActivityItem(
                        req_id=receipt.req_id,
                        agent=receipt.agent,
                        scope=receipt.scope,
                        price=str(receipt.price),
                        status="served",
                        source="chain",
                        created_at=served_at,
                        served_at=served_at,
                        receipt_hash=receipt.receipt_hash,
                    )
                )
            if len(batch) < CHAIN_RECEIPT_PAGE:
                break
    except ContractError as error:
        logger.warning("chain receipts unavailable", extra={"error_code": error.code})
    return receipts


@router.get("", response_model=ActivityPage)
async def activity(
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    claims: SessionClaims = Depends(require_owner),
    session: AsyncSession = Depends(get_db),
) -> ActivityPage:
    before: int | None = None
    if cursor is not None:
        try:
            before = int(cursor)
        except ValueError as error:
            raise MnemosError(400, "E_VALIDATION", "cursor must be a request id") from error
        if before < 1:
            raise MnemosError(400, "E_VALIDATION", "cursor must be a request id")

    statement = (
        select(ReadRequest)
        .where(ReadRequest.owner == claims.account)
        .order_by(ReadRequest.req_id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        statement = statement.where(ReadRequest.req_id < before)
    rows = list((await session.scalars(statement)).all())

    merged: dict[int, ActivityItem] = {row.req_id: _from_record(row) for row in rows}
    for item in await _chain_receipts(request, claims.account):
        if before is not None and item.req_id >= before:
            continue
        merged.setdefault(item.req_id, item)

    ordered = sorted(merged.values(), key=lambda item: item.req_id, reverse=True)
    has_more = len(ordered) > limit
    page = ordered[:limit]
    next_cursor = str(page[-1].req_id) if has_more and page else None
    return ActivityPage(items=page, next_cursor=next_cursor)


@router.get("/stream")
async def stream(
    request: Request,
    claims: SessionClaims = Depends(require_owner),
) -> StreamingResponse:
    services = get_services(request)
    owner = claims.account
    if services.publisher.subscriber_count(owner) >= MAX_SUBSCRIBERS_PER_OWNER:
        raise MnemosError(
            429, E_RATE_LIMITED, "too many activity stream connections for this account"
        )

    async def events() -> Any:
        async with services.publisher.subscribe(owner) as queue:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except asyncio.CancelledError:
                    break
                payload = json.dumps(event, separators=(",", ":"), default=str)
                yield f"event: {event.get('type', 'activity')}\ndata: {payload}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )
