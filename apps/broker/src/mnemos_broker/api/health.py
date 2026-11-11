"""Liveness and readiness checks. No secrets or raw errors are returned."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .. import __version__
from .deps import get_services

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "mnemos-broker", "version": __version__}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    services = get_services(request)

    async def check_db() -> bool:
        try:
            async with services.session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def check_chain() -> bool:
        try:
            await services.chain.ping()
            return True
        except Exception:
            return False

    database, chain, inference = await asyncio.gather(
        check_db(), check_chain(), services.inference.ready()
    )
    ready = database and chain and inference
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "components": {
                "database": database,
                "chain": chain,
                "near_ai_cloud": inference,
            },
        },
    )
