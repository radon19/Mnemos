"""The agent ask endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import AskRequest, AskResponse
from .deps import get_services, limit_ask

router = APIRouter(prefix="/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
async def ask(
    body: AskRequest,
    request: Request,
) -> AskResponse:
    services = get_services(request)
    await limit_ask(request, body.agent)
    return await services.pipeline.ask(body)


@router.post("/", response_model=AskResponse, include_in_schema=False)
async def ask_slash(
    body: AskRequest,
    request: Request,
) -> AskResponse:
    services = get_services(request)
    await limit_ask(request, body.agent)
    return await services.pipeline.ask(body)
