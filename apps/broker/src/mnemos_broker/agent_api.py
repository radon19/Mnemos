"""Real policy-bound payments through NEAR's Agent API.

A submitted operation is never payment evidence. Only a successful status with
the exact buyer, asset, amount, recipient and reference can unlock an answer.
Confidential Intents settlement has an intent hash, not necessarily a public tx.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import Any

import httpx

API_URLS = {"https://api.demo.agentsonintents.com", "https://api.agentsonintents.com"}


class AgentApiError(Exception):
    def __init__(self, code: str, *, status: int = 502) -> None:
        self.code = code
        self.status = status
        super().__init__(code)


class AgentApiClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        if base_url.rstrip("/") not in API_URLS:
            raise ValueError("Agent API credentials may only be sent to an official API host")
        self.http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key},
            timeout=35,
            follow_redirects=False,
        )

    async def __aenter__(self) -> AgentApiClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        grant: str | None = None,
        key: str | None = None,
        params: dict[str, str | int] | None = None,
    ) -> dict[str, Any]:
        headers = {}
        if grant:
            headers["X-Grant-Token"] = grant
        if key:
            headers["Idempotency-Key"] = key
        try:
            response = await self.http.request(
                method, path, json=body, headers=headers, params=params
            )
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise AgentApiError("E_AGENT_API_UNAVAILABLE") from error
        if not response.is_success:
            errors = payload.get("errors", []) if isinstance(payload, dict) else []
            code = errors[0].get("code") if errors and isinstance(errors[0], dict) else None
            if not isinstance(code, str) or not re.fullmatch(r"[a-z_]{1,80}", code):
                code = "E_AGENT_API_UNAVAILABLE"
            # Never forward arbitrary upstream text: it may contain credentials or payloads.
            raise AgentApiError(
                code, status=response.status_code if response.status_code < 500 else 502
            )
        if not isinstance(payload, dict):
            raise AgentApiError("E_AGENT_API_EVIDENCE")
        return payload

    async def settled(self, correlation: str, *, wait_seconds: float = 90) -> dict[str, Any]:
        deadline = monotonic() + wait_seconds
        while monotonic() < deadline:
            result = await self.request(
                "GET",
                "/v1/status",
                params={
                    "correlation_id": correlation,
                    "wait_ms": 3000,
                },
            )
            if result.get("correlation_id") != correlation:
                raise AgentApiError("E_AGENT_API_EVIDENCE")
            status = result.get("status")
            if status == "SUCCESS":
                return result
            if status in {"FAILED", "REFUNDED", "UNCERTAIN", "NEEDS_REVIEW"}:
                raise AgentApiError("E_PAYMENT_FAILED", status=409)
            await asyncio.sleep(0.2)
        raise AgentApiError("E_PAYMENT_PENDING", status=409)

    async def pay(
        self,
        *,
        agent: str,
        grant: str,
        asset: str,
        amount: str,
        recipient: str,
        reference: str,
        on_submitted: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        body = {
            "asset": asset,
            "amount": amount,
            "recipient": recipient,
            "reference": reference,
            "confidential": True,
        }
        operation = await self.request(
            "POST",
            f"/v1/agents/{agent}/transfer",
            body=body,
            grant=grant,
            key=reference,
        )
        correlation = operation.get("correlation_id")
        if not isinstance(correlation, str) or not correlation.startswith("op_"):
            raise AgentApiError("E_AGENT_API_EVIDENCE")
        if on_submitted is not None:
            await on_submitted(correlation)
        return await self.confirm(correlation, agent=agent, body=body)

    async def confirm(
        self, correlation: str, *, agent: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """Inspect an accepted payment without spending authorization or a new POST."""
        result = await self.settled(correlation)
        details = result.get("details", {})
        if not isinstance(details, dict) or not isinstance(details.get("request"), dict):
            raise AgentApiError("E_AGENT_API_EVIDENCE")
        request = details.get("request", {})
        if (
            result.get("agent_id") != agent
            or result.get("type") != "transfer"
            or details.get("action") != "transfer"
            or any(request.get(field) != value for field, value in body.items())
            or not details.get("intent_hash")
        ):
            raise AgentApiError("E_AGENT_API_EVIDENCE")
        return result
