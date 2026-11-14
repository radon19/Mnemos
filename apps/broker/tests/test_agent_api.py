from __future__ import annotations

import json

import pytest
import respx

BASE = "https://api.demo.agentsonintents.com"
AGENT = "a" * 64


def operation(status="SUCCESS", recipient="expert.near"):
    return {
        "agent_id": AGENT,
        "correlation_id": "op_live",
        "type": "transfer",
        "status": status,
        "failure_code": None,
        "details": {
            "action": "transfer",
            "request": {
                "asset": "usdc",
                "amount": "10000",
                "recipient": recipient,
                "reference": "mnemos:read-1",
                "confidential": True,
            },
            "intent_hash": "settled-intent",
        },
    }


@pytest.mark.asyncio
@respx.mock
async def test_purchase_waits_for_matching_settlement_not_202_confirmation():
    from mnemos_broker.agent_api import AgentApiClient

    post = respx.post(f"{BASE}/v1/agents/{AGENT}/transfer").respond(
        202, json=operation("PROCESSING")
    )
    status = respx.get(f"{BASE}/v1/status").respond(200, json=operation())
    async with AgentApiClient(BASE, "partner-secret") as api:
        result = await api.pay(
            agent=AGENT,
            grant="grant-secret",
            asset="usdc",
            amount="10000",
            recipient="expert.near",
            reference="mnemos:read-1",
        )
    assert result["status"] == "SUCCESS"
    assert len(status.calls) == 1
    request = post.calls[0].request
    assert request.headers["Idempotency-Key"] == "mnemos:read-1"
    assert request.headers["X-Grant-Token"] == "grant-secret"
    assert json.loads(request.content)["confidential"] is True


@pytest.mark.asyncio
@respx.mock
async def test_policy_error_is_preserved_without_secrets():
    from mnemos_broker.agent_api import AgentApiClient, AgentApiError

    respx.post(f"{BASE}/v1/agents/{AGENT}/transfer").respond(
        403,
        json={
            "errors": [
                {
                    "code": "policy_destination_denied",
                    "detail": "arbitrary upstream partner-secret grant-secret",
                    "layer": "policy",
                }
            ]
        },
    )
    async with AgentApiClient(BASE, "partner-secret") as api:
        with pytest.raises(AgentApiError) as error:
            await api.pay(
                agent=AGENT,
                grant="grant-secret",
                asset="usdc",
                amount="10000",
                recipient="bad.near",
                reference="mnemos:read-1",
            )
    assert error.value.code == "policy_destination_denied"
    assert "secret" not in str(error.value)


@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize(
    "kind",
    ["mismatched-recipient", "wrong-agent", "wrong-amount", "missing-intent", "needs-review"],
)
async def test_payment_evidence_must_match_the_exact_purchase(kind):
    from mnemos_broker.agent_api import AgentApiClient, AgentApiError

    data = operation()
    if kind == "mismatched-recipient":
        data["details"]["request"]["recipient"] = "attacker.near"
    if kind == "wrong-agent":
        data["agent_id"] = "b" * 64
    if kind == "wrong-amount":
        data["details"]["request"]["amount"] = "1"
    if kind == "missing-intent":
        data["details"]["intent_hash"] = None
    if kind == "needs-review":
        data["status"] = "NEEDS_REVIEW"
    respx.post(f"{BASE}/v1/agents/{AGENT}/transfer").respond(202, json=data)
    respx.get(f"{BASE}/v1/status").respond(200, json=data)
    async with AgentApiClient(BASE, "secret") as api:
        with pytest.raises(AgentApiError):
            await api.pay(
                agent=AGENT,
                grant="grant",
                asset="usdc",
                amount="10000",
                recipient="expert.near",
                reference="mnemos:read-1",
            )


def test_credentials_cannot_be_sent_to_an_arbitrary_host():
    from mnemos_broker.agent_api import AgentApiClient

    with pytest.raises(ValueError):
        AgentApiClient("https://attacker.invalid", "secret")
