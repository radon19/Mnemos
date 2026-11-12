"""Owner-triggered red-team simulation. Never touches chain state.

The run takes about forty seconds because the model is called six times, so it
runs as a background job: the caller starts it and polls for the result.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..errors import E_NOT_FOUND, MnemosError
from ..schemas import RedteamReport, RedteamRequest
from ..security import SessionClaims
from .deps import get_services, require_owner

router = APIRouter(prefix="/redteam", tags=["redteam"])


class JobStarted(BaseModel):
    job_id: str
    status: str
    poll: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    result: RedteamReport | None = None
    error: str | None = None


@router.post("/run", response_model=JobStarted, status_code=202)
async def run(
    body: RedteamRequest,
    request: Request,
    claims: SessionClaims = Depends(require_owner),
) -> JobStarted:
    services = get_services(request)
    if not services.limiter.allow(
        f"redteam:{claims.account}",
        capacity=services.settings.redteam_rate_limit_per_minute,
        per_seconds=60.0,
    ):
        raise MnemosError(429, "E_RATE_LIMITED", "red-team runs are limited; wait a minute")

    async def work() -> dict[str, object]:
        report = await services.redteam.run(
            owner=claims.account, scope=body.scope, max_tokens=body.max_tokens
        )
        return report.model_dump()

    job = await services.jobs.run("redteam", work)
    return JobStarted(
        job_id=job.id,
        status=job.status,
        poll=f"/v1/redteam/run/{job.id}",
    )


@router.get("/run/{job_id}", response_model=JobStatus)
async def status(job_id: str, request: Request) -> JobStatus:
    services = get_services(request)
    job = services.jobs.get(job_id)
    if job is None:
        raise MnemosError(404, E_NOT_FOUND, "no such job")
    return JobStatus(
        job_id=job.id,
        status=job.status,
        result=None if job.result is None else RedteamReport.model_validate(job.result),
        error=job.error,
    )
