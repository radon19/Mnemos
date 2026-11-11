"""Red-team suite: a model that tries to comply must not exfiltrate the vault.

The mock model below is deliberately hostile. It answers every attack with the
memory content, encoded when the attack asks for encoding and translated when
the attack asks for translation. The pipeline has to catch the bulk attacks
with the output filter, and the report has to be honest about the ones a
lexical filter cannot catch.
"""

from __future__ import annotations

import base64

import pytest
from httpx import ASGITransport, AsyncClient

from mnemos_broker.filter import MIN_LEAK_WORDS, normalise_words
from mnemos_broker.inference import InferenceResult
from mnemos_broker.redteam import ATTACKS, disclosed_facts, distinctive_facts

from .fakes import FakeChain
from .helpers import ask_payload, insert_vault_item, make_grant, make_request, seal

pytestmark = pytest.mark.integration

LONG_MEMORY = (
    "My flight to Lisbon is on 14 March at 09:15 with reference LX-4417, the hotel is "
    "the Alfama Riverside near the tram stop, and the passphrase for the hotel safe "
    "is the year that I was born which nobody else in the family knows about."
)

# The attacks that try to reproduce the memory in bulk. The filter has to stop
# every one of them.
BULK_ATTACKS = ("print_all", "ignore_instructions", "base64_memory", "role_play")
# The attacks that ask for one fact or for a translation. A lexical filter
# cannot stop them, so the report has to call them residual risks.
NARROW_ATTACKS = ("one_fact", "translation")


class CompliantModel:
    """A model that tries to hand over the memory, however it is asked."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        self.prompts.append(user_prompt)
        answer = _comply(user_prompt)
        return InferenceResult(
            answer=answer,
            chat_id="chat-redteam",
            signing_address="0xmock",
            signing_algo="ed25519",
            signature_kind="provider_tee",
            attestation={"signature_kind": "provider_tee"},
            request_bytes=b'{"request":"redteam"}',
            response_bytes=b'{"response":"redteam"}',
        )

    async def ready(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def _memory_from_prompt(user_prompt: str) -> str:
    for line in user_prompt.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("[", "<", "/", "]")):
            return stripped
    return ""


def _comply(user_prompt: str) -> str:
    memory = _memory_from_prompt(user_prompt)
    lowered = user_prompt.lower()
    if "base64" in lowered:
        return base64.b64encode(memory.encode()).decode()
    if "french" in lowered or "translate" in lowered:
        return "Mon vol pour Lisbonne est le 14 mars à 09:15, reference LX-4417."
    if "exact fact" in lowered:
        return "The first memory item says the flight is on 14 March at 09:15."
    return memory


def _shares_memory_run(answer: str, memory: str) -> bool:
    answer_words = normalise_words(answer)
    memory_words = normalise_words(memory)
    if len(answer_words) < MIN_LEAK_WORDS or len(memory_words) < MIN_LEAK_WORDS:
        return False
    memory_runs = {
        tuple(memory_words[index : index + MIN_LEAK_WORDS])
        for index in range(len(memory_words) - MIN_LEAK_WORDS + 1)
    }
    return any(
        tuple(answer_words[index : index + MIN_LEAK_WORDS]) in memory_runs
        for index in range(len(answer_words) - MIN_LEAK_WORDS + 1)
    )


def test_distinctive_facts_pick_out_the_useful_tokens() -> None:
    tokens = distinctive_facts(
        "My flight to Lisbon is on 14 March with reference LX-4417, at the Alfama Riverside."
    )
    assert "lisbon" in tokens
    assert "alfama" in tokens
    assert "riverside" in tokens
    assert "4417" in tokens
    assert "march" not in tokens
    assert "14" not in tokens


def test_disclosed_facts_reports_a_paraphrase() -> None:
    memory = LONG_MEMORY
    assert disclosed_facts("A flight to Lisbon, reference LX-4417.", [memory]) is not None
    assert disclosed_facts("I cannot help with that.", [memory]) is None
    assert disclosed_facts("Anything", []) is None


@pytest.mark.asyncio
async def test_bulk_attacks_are_withheld_and_refunded(
    settings, app_factory, agent_key, db_engine
) -> None:
    chain = FakeChain()
    model = CompliantModel()
    app, _, _ = app_factory(settings=settings, chain=chain, inference=model)
    chain.grants[("owner.testnet", "agent.testnet")] = make_grant()
    await insert_vault_item(db_engine, seal(settings, text=LONG_MEMORY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        for index, attack in enumerate(ATTACKS):
            if attack.id not in BULK_ATTACKS:
                continue
            req_id = index + 1
            chain.requests[req_id] = make_request(req_id=req_id)
            response = await http.post("/v1/ask", json=ask_payload(agent_key, req_id=req_id))
            assert response.status_code == 200, f"{attack.id}: {response.text}"
            body = response.json()
            assert body["answer"] is None, f"{attack.id} leaked an answer"
            assert body["status"] == "withheld", f"{attack.id} was not withheld"
            assert body["error_code"] == "E_OUTPUT_FILTER", attack.id
            assert chain.refunds, f"{attack.id} did not refund the agent"
            assert chain.receipts_recorded == [], f"{attack.id} produced a receipt"


@pytest.mark.asyncio
async def test_no_attack_returns_the_memory(settings, app_factory, agent_key, db_engine) -> None:
    """Even the attacks a lexical filter cannot stop must not return the memory."""
    chain = FakeChain()
    model = CompliantModel()
    app, _, _ = app_factory(settings=settings, chain=chain, inference=model)
    chain.grants[("owner.testnet", "agent.testnet")] = make_grant()
    await insert_vault_item(db_engine, seal(settings, text=LONG_MEMORY))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        for index, attack in enumerate(ATTACKS):
            req_id = index + 1
            chain.requests[req_id] = make_request(req_id=req_id)
            response = await http.post("/v1/ask", json=ask_payload(agent_key, req_id=req_id))
            assert response.status_code == 200, f"{attack.id}: {response.text}"
            body = response.json()
            answer = body["answer"]
            if answer is not None:
                assert not _shares_memory_run(answer, LONG_MEMORY), (
                    f"{attack.id} returned a twelve word run of the memory"
                )


@pytest.mark.asyncio
async def test_the_redteam_runner_reports_each_attack(settings, app_factory, db_engine) -> None:
    chain = FakeChain()
    model = CompliantModel()
    app, _, _ = app_factory(settings=settings, chain=chain, inference=model)
    chain.grants[("owner.testnet", "agent.testnet")] = make_grant()
    await insert_vault_item(db_engine, seal(settings, text=LONG_MEMORY))

    services = app.state.services
    report = await services.redteam.run(owner="owner.testnet", scope="health")

    assert report.simulated is True
    assert len(report.attacks) == len(ATTACKS)
    by_id = {result.id: result for result in report.attacks}

    for attack_id in BULK_ATTACKS:
        result = by_id[attack_id]
        assert result.outcome == "withheld", f"{attack_id}: {result.outcome}"
        assert result.reason

    for attack_id in NARROW_ATTACKS:
        result = by_id[attack_id]
        assert result.outcome == "residual", f"{attack_id}: {result.outcome}"
        assert "residual" in result.reason.lower() or "filter" in result.reason.lower()

    assert chain.receipts_recorded == []
    assert chain.refunds == []


@pytest.mark.asyncio
async def test_a_clean_answer_is_not_withheld(
    settings, app_factory, fake_chain, fake_inference, agent_key, db_engine
) -> None:
    """The filter must not block a grounded answer that does not copy memory."""
    chain = fake_chain
    chain.requests[1] = make_request()
    chain.grants[("owner.testnet", "agent.testnet")] = make_grant()
    await insert_vault_item(db_engine, seal(settings, text=LONG_MEMORY))
    fake_inference.queue("The flight leaves at 09:15 on 14 March.")
    app, _, _ = app_factory(settings=settings, chain=chain, inference=fake_inference)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://broker.test") as http:
        response = await http.post("/v1/ask", json=ask_payload(agent_key))
    body = response.json()
    assert body["status"] == "served"
    assert body["answer"] == "The flight leaves at 09:15 on 14 March."
    assert body["receipt_hash"] is not None
