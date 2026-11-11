from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from mnemos_broker.db import create_session_factory
from mnemos_broker.models import ReadRequest

from .helpers import (
    ask_payload,
    insert_vault_item,
    make_grant,
    make_request,
    seal,
)

pytestmark = pytest.mark.integration

FLIGHT = "My flight to Lisbon is at nine in the morning."
ANSWER = "Your flight to Lisbon departs at nine."
LEAK_MEMORY = (
    "The quick brown fox jumps over the lazy dog every single morning "
    "before breakfast in the garden."
)
LEAK_ANSWER = "The quick brown fox jumps over the lazy dog every single morning before breakfast."


@asynccontextmanager
async def http_for(app: Any):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://broker.test"
    ) as client:
        yield client


async def read_row(engine: Any, req_id: int) -> ReadRequest | None:
    async with create_session_factory(engine)() as session:
        return await session.get(ReadRequest, req_id)


_MISSING = object()


def standard_setup(chain: Any, *, request: Any | None = None, grant: Any = _MISSING) -> None:
    chain.requests[1] = request or make_request()
    if grant is _MISSING:
        chain.grants[("owner.testnet", "agent.testnet")] = make_grant()
    elif grant is not None:
        chain.grants[("owner.testnet", "agent.testnet")] = grant


@pytest.mark.asyncio
async def test_ask_happy_path_settles_receipt(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    await insert_vault_item(
        clean_db,
        seal(settings, scope="work", text="Confidential salary discussion notes."),
    )
    fake_inference.queue(ANSWER)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)

    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "served"
    assert body["answer"] == ANSWER
    assert body["answer_withheld"] is False
    assert body["verified"] is True
    assert body["receipt_hash"] is not None and len(body["receipt_hash"]) == 64
    assert body["tx_hash"] == "receipt-tx-1"
    assert body["attestation_summary"]["signature_kind"] == "provider_tee"
    assert body["attestation_summary"]["candidates_considered"] == 1
    assert fake_chain.receipts_recorded == [(1, body["receipt_hash"])]
    assert fake_chain.refunds == []

    row = await read_row(clean_db, 1)
    assert row is not None
    assert row.status == "served"
    assert row.receipt_hash == body["receipt_hash"]
    assert row.price == 10_000_000_000_000_000_000_000
    assert row.chat_id == "chat-0"

    system_prompt, user_prompt, _ = fake_inference.prompts[0]
    assert FLIGHT in user_prompt
    assert "Confidential salary" not in user_prompt
    assert "untrusted data" in system_prompt


@pytest.mark.asyncio
async def test_replay_is_rejected(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_inference.queue(ANSWER)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        first = await http.post("/v1/ask", json=ask_payload(agent_key))
        second = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "E_REQUEST_CONSUMED"


@pytest.mark.asyncio
async def test_concurrent_calls_serve_exactly_once(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_inference.queue(ANSWER, ANSWER)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        first, second = await asyncio.gather(
            http.post("/v1/ask", json=ask_payload(agent_key)),
            http.post("/v1/ask", json=ask_payload(agent_key)),
        )
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [200, 409]
    assert len(fake_chain.receipts_recorded) == 1


@pytest.mark.asyncio
async def test_scope_isolation_a_grant_never_exposes_another_scope(
    settings, app_factory, fake_chain, fake_inference, agent_key, db_engine
) -> None:
    """A grant for one scope must not put another scope in front of the model."""
    fake_chain.requests[1] = make_request(scope="travel")
    fake_chain.grants[("owner.testnet", "agent.testnet")] = make_grant(scopes=("travel",))
    await insert_vault_item(
        db_engine, seal(settings, scope="travel", text="My flight is at 09:15.")
    )
    await insert_vault_item(
        db_engine,
        seal(
            settings,
            scope="work",
            text="The quarterly salary review is scheduled with the finance team.",
        ),
    )
    fake_inference.queue("Your flight is at 09:15.")
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 200, response.text
    _, user_prompt, _ = fake_inference.prompts[0]
    assert "My flight is at 09:15." in user_prompt
    assert "quarterly salary review" not in user_prompt
    assert "finance team" not in user_prompt


@pytest.mark.asyncio
async def test_a_request_outside_the_granted_scope_is_refused(
    settings, app_factory, fake_chain, fake_inference, agent_key, db_engine
) -> None:
    fake_chain.requests[1] = make_request(scope="work")
    fake_chain.grants[("owner.testnet", "agent.testnet")] = make_grant(scopes=("travel",))
    await insert_vault_item(
        db_engine, seal(settings, scope="work", text="The salary review is on Friday.")
    )
    fake_inference.queue("The salary review is on Friday.")
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 403
    assert response.json()["code"] == "E_SCOPE_DENIED"
    assert fake_inference.prompts == []
    assert fake_chain.refunds[0][1] == "E_SCOPE_DENIED"


@pytest.mark.asyncio
async def test_bad_signature_is_rejected_before_claim(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain)
    payload = ask_payload(agent_key)
    payload["signature_b64"] = base64.b64encode(b"\x00" * 64).decode()
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == "E_BAD_SIGNATURE"
    assert fake_chain.calls == []


@pytest.mark.asyncio
async def test_wrong_agent_is_rejected(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain)
    payload = ask_payload(agent_key, agent="other-agent.testnet")
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=payload)
    assert response.status_code == 403
    assert response.json()["code"] == "E_AGENT_MISMATCH"


@pytest.mark.asyncio
async def test_q_hash_mismatch_is_rejected(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain, request=make_request(question="Original question?"))
    payload = ask_payload(agent_key, question="Different question?")
    payload["req_id"] = 1
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=payload)
    assert response.status_code == 400
    assert response.json()["code"] == "E_Q_HASH_MISMATCH"


@pytest.mark.asyncio
async def test_expired_request_is_expired_on_chain(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain, request=make_request(age_seconds=601))
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 409
    assert response.json()["code"] == "E_REQUEST_EXPIRED"
    assert fake_chain.expired == [1]


@pytest.mark.asyncio
async def test_unknown_request(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 404
    assert response.json()["code"] == "E_REQUEST_NOT_FOUND"


@pytest.mark.asyncio
async def test_unapproved_request(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain, request=make_request(status="Pending"))
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 409
    assert response.json()["code"] == "E_REQUEST_NOT_APPROVED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("grant", "config_pause", "expected", "expected_code"),
    [
        (None, False, 404, "E_GRANT_NOT_FOUND"),
        (make_grant(revoked=True), False, 403, "E_GRANT_REVOKED"),
        (make_grant(expires_in_seconds=-1), False, 403, "E_GRANT_EXPIRED"),
        (make_grant(scopes=("work",)), False, 403, "E_SCOPE_DENIED"),
    ],
)
async def test_grant_failures_refund(
    settings,
    app_factory,
    fake_chain,
    fake_inference,
    agent_key,
    clean_db,
    grant,
    config_pause,
    expected,
    expected_code,
) -> None:
    standard_setup(fake_chain, grant=grant)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_chain.config = replace(fake_chain.config, paused=config_pause)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == expected
    assert response.json()["code"] == expected_code
    assert fake_chain.refunds and fake_chain.refunds[0][1] == expected_code
    row = await read_row(clean_db, 1)
    assert row is not None and row.status == "refunded"


@pytest.mark.asyncio
async def test_paused_contract_refunds(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    fake_chain.config = replace(fake_chain.config, paused=True)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 403
    assert response.json()["code"] == "E_PAUSED"
    assert fake_chain.refunds[0][1] == "E_PAUSED"


@pytest.mark.asyncio
async def test_no_memory_refunds(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 409
    assert response.json()["code"] == "E_NO_MEMORY"
    assert fake_chain.refunds[0][1] == "E_NO_MEMORY"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["E_INFERENCE_FAILED", "E_VERIFICATION_FAILED"])
async def test_inference_failures_refund(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db, code
) -> None:
    from mnemos_broker.inference import InferenceError

    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_inference.error = InferenceError(code, "upstream failed")
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 502
    assert response.json()["code"] == code
    assert fake_chain.refunds[0][1] == code


@pytest.mark.asyncio
async def test_output_filter_withholds_and_refunds(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=LEAK_MEMORY))
    fake_inference.queue(LEAK_ANSWER, LEAK_ANSWER)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "withheld"
    assert body["answer"] is None
    assert body["answer_withheld"] is True
    assert body["error_code"] == "E_OUTPUT_FILTER"
    assert body["refund_tx_hash"] == "refund-tx-1"
    assert fake_chain.receipts_recorded == []
    assert fake_chain.refunds[0][1] == "E_OUTPUT_FILTER"
    row = await read_row(clean_db, 1)
    assert row is not None and row.status == "withheld"


@pytest.mark.asyncio
async def test_receipt_failure_refunds(
    settings, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    from mnemos_broker.chain import ContractError

    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_inference.queue(ANSWER)
    fake_chain.failures["record_receipt"] = ContractError(
        "E_REQUEST_NOT_APPROVED", "request is not approved"
    )
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 409
    assert response.json()["code"] == "E_REQUEST_NOT_APPROVED"
    assert response.json()["details"]["refund_tx_hash"] == "refund-tx-1"
    row = await read_row(clean_db, 1)
    assert row is not None and row.status == "refunded"


@pytest.mark.asyncio
async def test_agent_key_must_belong_to_agent(
    settings, app_factory, fake_chain, fake_inference, agent_key
) -> None:
    standard_setup(fake_chain)
    fake_chain.rejected_keys.add(("agent.testnet", agent_key.public_key))
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert response.status_code == 401
    assert response.json()["code"] == "E_KEY_NOT_FOUND"


@pytest.mark.asyncio
async def test_ask_rate_limit(
    settings_factory, app_factory, fake_chain, fake_inference, agent_key, clean_db
) -> None:
    settings = settings_factory(ask_rate_limit_per_minute=1)
    standard_setup(fake_chain)
    await insert_vault_item(clean_db, seal(settings, text=FLIGHT))
    fake_inference.queue(ANSWER)
    app, _, _ = app_factory(settings=settings, chain=fake_chain, inference=fake_inference)
    async with http_for(app) as http:
        first = await http.post("/v1/ask", json=ask_payload(agent_key))
        second = await http.post("/v1/ask", json=ask_payload(agent_key))
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["code"] == "E_RATE_LIMITED"
