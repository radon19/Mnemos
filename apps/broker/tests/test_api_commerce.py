from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

import pytest
import respx
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from mnemos_broker.security import SESSION_COOKIE, sign_session

from .helpers import insert_vault_item, seal

pytestmark = pytest.mark.integration
BASE = "https://api.demo.agentsonintents.com"
BUYER = "a" * 64
SELLER = "b" * 64


def configured(settings_factory):
    return settings_factory(
        agent_api_enabled=True,
        agent_api_key=SecretStr("partner-secret"),
        agent_api_buyer_id=BUYER,
        agent_api_buyer_grant=SecretStr("buyer-secret"),
        agent_api_seller_id=SELLER,
        agent_api_seller_grant=SecretStr("seller-secret"),
        agent_api_buyer_account="buyer.near",
        agent_api_seller_account="expert.near",
        agent_api_asset="usdc",
    )


def payment(read_id, *, refund=False):
    return {
        "agent_id": SELLER if refund else BUYER,
        "correlation_id": "op_refund" if refund else "op_paid",
        "type": "transfer",
        "status": "SUCCESS",
        "failure_code": None,
        "details": {
            "action": "transfer",
            "request": {
                "asset": "usdc",
                "amount": "10000",
                "recipient": "buyer.near" if refund else "expert.near",
                "confidential": True,
                "reference": f"mnemos-{'refund' if refund else 'read'}:{read_id}",
            },
            "intent_hash": "real-api-intent",
        },
    }


def cookie(settings):
    return {
        SESSION_COOKIE: sign_session(
            "owner.testnet", settings.session_secret_bytes, ttl=timedelta(minutes=30)
        )[0]
    }


@pytest.mark.asyncio
@respx.mock
async def test_paid_api_answer_waits_for_settlement_and_cannot_be_replayed(
    settings_factory, app_factory, fake_inference, clean_db
):
    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="Lisbon has pleasant quiet neighborhoods.")
    )
    fake_inference.queue("Try Campo de Ourique.")
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    pay = respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(202, json=payment(read_id))
    respx.get(f"{BASE}/v1/status").respond(200, json=payment(read_id))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as client:
        body = {"read_id": read_id, "scope": "expertise", "question": "Where should I stay?"}
        first = await client.post("/v1/commerce/ask", json=body)
        assert first.status_code == 200, first.text
        assert first.json()["answer"] == "Try Campo de Ourique."
        assert first.json()["payment"]["details"]["intent_hash"] == "real-api-intent"
        assert first.json()["network"] == "mainnet"
        again = await client.post("/v1/commerce/ask", json=body)
        assert again.status_code == 409
    assert len(pay.calls) == 1
    assert len(fake_inference.prompts) == 1


@pytest.mark.asyncio
@respx.mock
async def test_denied_payment_never_decrypts_or_calls_model(
    settings_factory, app_factory, fake_inference
):
    settings = configured(settings_factory)
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(
        403, json={"errors": [{"code": "agent_grant_required"}]}
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as client:
        response = await client.post(
            "/v1/commerce/ask",
            json={"read_id": str(uuid.uuid4()), "scope": "expertise", "question": "Where?"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "agent_grant_required"
    assert fake_inference.prompts == []


@pytest.mark.asyncio
@respx.mock
async def test_unverified_inference_refunds_real_api_payment(
    settings_factory, app_factory, fake_inference, clean_db
):
    from mnemos_broker.inference import InferenceError

    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="My private expert knowledge.")
    )
    fake_inference.error = InferenceError("E_VERIFICATION_FAILED", "bad signature")
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(202, json=payment(read_id))
    refund = respx.post(f"{BASE}/v1/agents/{SELLER}/transfer").respond(
        202, json=payment(read_id, refund=True)
    )
    respx.get(f"{BASE}/v1/status").mock(
        side_effect=lambda request: __import__("httpx").Response(
            200,
            json=payment(read_id, refund=request.url.params.get("correlation_id") == "op_refund"),
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as client:
        result = await client.post(
            "/v1/commerce/ask", json={"read_id": read_id, "scope": "expertise", "question": "What?"}
        )
    assert result.status_code == 502
    assert result.json()["code"] == "E_VERIFICATION_FAILED"
    assert result.json()["details"]["refund_status"] == "SUCCESS"
    assert len(refund.calls) == 1


@pytest.mark.asyncio
async def test_private_scope_and_other_owner_cannot_use_operator_wallet(
    settings_factory, app_factory
):
    settings = configured(settings_factory)
    app, _, _ = app_factory(settings=settings)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as client:
        result = await client.post(
            "/v1/commerce/ask",
            json={"read_id": str(uuid.uuid4()), "scope": "private", "question": "secret?"},
        )
        assert result.status_code == 403

        assert result.json()["code"] == "E_SCOPE_DENIED"
        client.cookies.set(
            SESSION_COOKIE,
            sign_session("other.testnet", settings.session_secret_bytes, ttl=timedelta(minutes=30))[
                0
            ],
        )
        result = await client.get("/v1/commerce/status")
        assert result.status_code == 403


@pytest.mark.asyncio
@respx.mock
async def test_concurrent_duplicate_cannot_double_pay_or_double_generate(
    settings_factory, app_factory, fake_inference, clean_db, monkeypatch
):
    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="Quiet Lisbon expertise.")
    )
    fake_inference.queue("Stay near the market.")
    entered, release = asyncio.Event(), asyncio.Event()
    original = fake_inference.complete

    async def waiting(**kwargs):
        entered.set()
        await release.wait()
        return await original(**kwargs)

    monkeypatch.setattr(fake_inference, "complete", waiting)
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    pay = respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(202, json=payment(read_id))
    respx.get(f"{BASE}/v1/status").respond(200, json=payment(read_id))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as http:
        body = {"read_id": read_id, "scope": "expertise", "question": "Where?"}
        first = asyncio.create_task(http.post("/v1/commerce/ask", json=body))
        await asyncio.wait_for(entered.wait(), 3)
        try:
            second = await asyncio.wait_for(http.post("/v1/commerce/ask", json=body), 3)
            assert second.status_code == 409, second.text
            assert second.json()["code"] == "E_READ_BUSY"
        finally:
            release.set()
            completed = await first
        assert completed.status_code == 200
    assert len(pay.calls) == 1
    assert len(fake_inference.prompts) == 1


@pytest.mark.asyncio
@respx.mock
async def test_crash_after_external_refund_never_turns_into_a_free_answer(
    settings_factory, app_factory, fake_inference, clean_db, monkeypatch
):
    from mnemos_broker.agent_api import AgentApiClient
    from mnemos_broker.inference import InferenceError

    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="Quiet Lisbon expertise.")
    )
    fake_inference.error = InferenceError("E_VERIFICATION_FAILED", "bad signature")
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(202, json=payment(read_id))
    refund = respx.post(f"{BASE}/v1/agents/{SELLER}/transfer").respond(
        202, json=payment(read_id, refund=True)
    )
    respx.get(f"{BASE}/v1/status").mock(
        side_effect=lambda request: __import__("httpx").Response(
            200,
            json=payment(read_id, refund=request.url.params.get("correlation_id") == "op_refund"),
        )
    )
    original = AgentApiClient.pay
    crashed = False

    async def crash_after_refund(self, **kwargs):
        nonlocal crashed
        result = await original(self, **kwargs)
        if kwargs["reference"].startswith("mnemos-refund:") and not crashed:
            crashed = True
            raise asyncio.CancelledError()
        return result

    monkeypatch.setattr(AgentApiClient, "pay", crash_after_refund)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as http:
        body = {"read_id": read_id, "scope": "expertise", "question": "Where?"}
        from mnemos_broker.commerce import CommerceService

        with pytest.raises(asyncio.CancelledError):
            await CommerceService(app.state.services.pipeline).ask(
                owner="owner.testnet",
                read_id=uuid.UUID(read_id),
                scope="expertise",
                question="Where?",
            )
        fake_inference.error = None
        fake_inference.queue("This answer must never be delivered after refund.")
        resumed = await http.post("/v1/commerce/ask", json=body)
    assert resumed.status_code == 502, resumed.text
    assert resumed.json()["details"]["refund_status"] == "SUCCESS"
    assert len(fake_inference.prompts) == 1
    assert len(refund.calls) >= 1


@pytest.mark.asyncio
@respx.mock
async def test_accepted_payment_recovers_by_operation_id_after_grant_revocation(
    settings_factory, app_factory, fake_inference, clean_db
):
    import httpx

    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="Quiet Lisbon expertise.")
    )
    fake_inference.queue("Stay near the market.")
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    pay = respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").mock(
        side_effect=[
            httpx.Response(202, json=payment(read_id)),
            httpx.Response(403, json={"errors": [{"code": "agent_grant_required"}]}),
        ]
    )
    respx.get(f"{BASE}/v1/status").mock(
        side_effect=[
            httpx.Response(503, json={"errors": [{"code": "provider_unavailable"}]}),
            httpx.Response(200, json=payment(read_id)),
        ]
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as http:
        body = {"read_id": read_id, "scope": "expertise", "question": "Where?"}
        first = await http.post("/v1/commerce/ask", json=body)
        assert first.status_code == 502
        resumed = await http.post("/v1/commerce/ask", json=body)
    assert resumed.status_code == 200, resumed.text
    assert len(pay.calls) == 1
    assert resumed.json()["payment"]["correlation_id"] == "op_paid"


@pytest.mark.asyncio
@respx.mock
async def test_owner_refund_by_id_survives_reload_and_session_secret_rotation(
    settings_factory, app_factory, fake_inference, clean_db
):
    import httpx

    from mnemos_broker.inference import InferenceError

    settings = configured(settings_factory)
    await insert_vault_item(
        clean_db, seal(settings, scope="expertise", text="Quiet Lisbon expertise.")
    )
    fake_inference.error = InferenceError("E_VERIFICATION_FAILED", "bad signature")
    app, _, _ = app_factory(settings=settings, inference=fake_inference)
    read_id = str(uuid.uuid4())
    respx.post(f"{BASE}/v1/agents/{BUYER}/transfer").respond(202, json=payment(read_id))
    respx.post(f"{BASE}/v1/agents/{SELLER}/transfer").mock(
        side_effect=[
            httpx.Response(503, json={"errors": [{"code": "provider_unavailable"}]}),
            httpx.Response(202, json=payment(read_id, refund=True)),
        ]
    )
    respx.get(f"{BASE}/v1/status").mock(
        side_effect=lambda request: httpx.Response(
            200,
            json=payment(read_id, refund=request.url.params.get("correlation_id") == "op_refund"),
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test", cookies=cookie(settings)
    ) as http:
        first = await http.post(
            "/v1/commerce/ask",
            json={
                "read_id": read_id,
                "scope": "expertise",
                "question": "A question I later forgot",
            },
        )
        assert first.json()["details"]["refund_status"] == "PENDING"
    rotated = settings.model_copy(
        update={"session_secret": SecretStr("new-session-secret-" + "z" * 32)}
    )
    recovered_app, _, _ = app_factory(settings=rotated, inference=fake_inference)
    async with AsyncClient(
        transport=ASGITransport(app=recovered_app),
        base_url="http://broker.test",
        cookies=cookie(rotated),
    ) as http:
        result = await http.post("/v1/commerce/refund", json={"read_id": read_id})
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "refunded"
    assert len(fake_inference.prompts) == 1
