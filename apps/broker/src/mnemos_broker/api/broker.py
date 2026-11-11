"""Public broker identity. The setup screen compares this fingerprint on chain."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import BrokerPubkeyResponse
from .deps import get_services

router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/pubkey", response_model=BrokerPubkeyResponse)
async def pubkey(request: Request) -> BrokerPubkeyResponse:
    services = get_services(request)
    settings = services.settings
    return BrokerPubkeyResponse(
        account=settings.broker_near_account,
        public_key_b64=services.broker_public_key_b64,
        fingerprint=services.broker_fingerprint,
        recipient=settings.broker_recipient,
        network=settings.near_network,
        contract_id=settings.mnemos_contract_id,
    )
