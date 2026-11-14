"""Owner-authorized mainnet expertise offer, distinct from the testnet rail."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from ..agent_api import AgentApiError
from ..commerce import CommerceService
from ..errors import MnemosError
from .deps import get_services, limit_ask, require_owner

router = APIRouter(prefix="/commerce", tags=["commerce"])


class CommerceAsk(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    read_id: uuid.UUID
    scope: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=2000)


class CommerceRefund(BaseModel):
    model_config = ConfigDict(extra="forbid")
    read_id: uuid.UUID


def service_for_owner(request: Request) -> CommerceService:
    owner = require_owner(request)
    services = get_services(request)
    if owner.account != services.settings.mnemos_owner_account:
        raise MnemosError(
            403, "E_OWNER_MISMATCH", "Only the configured offer owner can use this laptop wallet."
        )
    return CommerceService(services.pipeline)


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    service = service_for_owner(request)
    try:
        return await service.status()
    except AgentApiError as error:
        raise MnemosError(
            error.status, error.code, "Agent API status is unavailable; no payment was attempted."
        ) from error


@router.post("/ask")
async def ask(request: Request, body: CommerceAsk) -> dict[str, Any]:
    service = service_for_owner(request)
    await limit_ask(request, service.settings.agent_api_buyer_id)
    return await service.ask(
        owner=service.settings.mnemos_owner_account,
        read_id=body.read_id,
        scope=body.scope,
        question=body.question,
    )


@router.post("/refund")
async def refund(request: Request, body: CommerceRefund) -> dict[str, Any]:
    service = service_for_owner(request)
    await limit_ask(request, service.settings.agent_api_buyer_id)
    return await service.refund(owner=service.settings.mnemos_owner_account, read_id=body.read_id)
