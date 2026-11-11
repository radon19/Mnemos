"""Owner-triggered red-team simulation. Never touches chain state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..errors import E_RATE_LIMITED, MnemosError
from ..schemas import RedteamReport, RedteamRequest
from ..security import SessionClaims
from .deps import get_services, require_owner

router = APIRouter(prefix="/redteam", tags=["redteam"])


@router.post("/run", response_model=RedteamReport)
async def run(
    body: RedteamRequest,
    request: Request,
    claims: SessionClaims = Depends(require_owner),
) -> RedteamReport:
    services = get_services(request)
    if not services.limiter.allow(
        f"redteam:{claims.account}",
        capacity=services.settings.redteam_rate_limit_per_minute,
        per_seconds=60.0,
    ):
        raise MnemosError(429, E_RATE_LIMITED, "red-team runs are limited; wait a minute")
    return await services.redteam.run(
        owner=claims.account, scope=body.scope, max_tokens=body.max_tokens
    )
