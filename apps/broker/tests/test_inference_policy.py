from __future__ import annotations

import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from mnemos_broker.inference import InferenceError, NearAiInferenceEngine


def verified(kind="provider_tee", count=1):
    signer = NS(signing_address="model-signer", signing_algo="ed25519")
    attestation = NS(
        deployment=NS(
            runtime_measurements=NS(os_image_hash="os", compose_hash="compose"),
            compose_manager=None,
            app_compose="measured-config",
        ),
        tcb_status="UpToDate",
        advisory_ids=[],
        deployment_provenance="not_checked",
        gpu_evidence="verified",
    )
    return NS(
        signature_kind=kind,
        signature=NS(signer=signer),
        attestation=attestation,
        attestations=tuple(attestation for _ in range(count)),
    )


def sdk(monkeypatch, result, error=None):
    clients = []

    def create(*args, **kwargs):
        completion = NS(
            id="chat-actual",
            model="test-model",
            usage=None,
            choices=[NS(message=NS(content="A grounded answer."), finish_reason="stop")],
        )
        client = NS(
            chat=NS(completions=NS(create=AsyncMock(return_value=completion))),
            verify_response=AsyncMock(return_value=result, side_effect=error),
            aclose=AsyncMock(),
        )
        clients.append(client)
        return client

    monkeypatch.setattr("mnemos_broker.inference.InferenceClient", create)
    return clients


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,count", [("gateway", 1), ("provider_tee", 0), ("provider_tee", 2)])
async def test_no_answer_for_gateway_or_missing_or_ambiguous_model_evidence(
    settings, monkeypatch, kind, count
):
    sdk(monkeypatch, verified(kind, count))
    engine = NearAiInferenceEngine(settings)
    with pytest.raises(InferenceError) as error:
        await engine.complete(system_prompt="system", user_prompt="private", max_tokens=128)
    assert error.value.code == "E_VERIFICATION_FAILED"


@pytest.mark.asyncio
async def test_each_read_has_a_new_closed_sdk_session(settings, monkeypatch):
    clients = sdk(monkeypatch, verified())
    engine = NearAiInferenceEngine(settings)
    for _ in range(2):
        result = await engine.complete(
            system_prompt="system", user_prompt="private", max_tokens=128
        )
        assert result.answer == "A grounded answer."
        assert result.attestation["fresh_preflight"] is True
    assert len(clients) == 2
    assert all(client.aclose.await_count == 1 for client in clients)


@pytest.mark.asyncio
async def test_invalid_signature_releases_no_answer_and_closes_session(settings, monkeypatch):
    clients = sdk(monkeypatch, verified(), error=ValueError("invalid signature"))
    engine = NearAiInferenceEngine(settings)
    with pytest.raises(InferenceError) as error:
        await engine.complete(system_prompt="system", user_prompt="private", max_tokens=128)
    assert error.value.code == "E_VERIFICATION_FAILED"
    assert clients[-1].aclose.await_count == 1


@pytest.mark.asyncio
async def test_qwen_answer_budget_is_not_consumed_by_hidden_reasoning(settings, monkeypatch):
    settings = settings.model_copy(update={"nearai_model": "Qwen/Qwen3.8-27B"})
    clients = sdk(monkeypatch, verified())
    engine = NearAiInferenceEngine(settings)
    client = engine._new_client()

    async def model(**kwargs):
        # Characterize the provider behavior seen in the verified live response:
        # with thinking enabled, all 256 completion tokens went to reasoning.
        direct_answer = (
            kwargs.get("extra_body", {}).get("chat_template_kwargs", {}).get("enable_thinking")
            is False
        )
        return NS(
            id="chat-bounded",
            model=settings.nearai_model,
            usage=None,
            choices=[
                NS(
                    message=NS(
                        content="Stay in Campo de Ourique; use the metro." if direct_answer else ""
                    ),
                    finish_reason="stop" if direct_answer else "length",
                )
            ],
        )

    client.chat.completions.create.side_effect = model
    monkeypatch.setattr(engine, "_new_client", lambda: client)
    result = await engine.complete(
        system_prompt="Answer only from memory", user_prompt="Public sample", max_tokens=256
    )
    assert result.answer == "Stay in Campo de Ourique; use the metro."
    projection = json.loads(result.request_bytes)
    assert projection["max_tokens"] == 256
    assert projection["chat_template_kwargs"] == {"enable_thinking": False}
    assert result.signature_kind == "provider_tee"
    assert result.attestation["fresh_preflight"] is True
    assert clients[-1].aclose.await_count == 1
