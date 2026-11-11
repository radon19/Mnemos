"""Deterministic stand-ins for the chain, inference and clock used by tests."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from mnemos_broker.chain import (
    ChainBroker,
    ChainConfig,
    ChainGrant,
    ChainReceipt,
    ChainRequest,
    ContractError,
)
from mnemos_broker.errors import E_KEY_NOT_FOUND, MnemosError
from mnemos_broker.inference import InferenceError, InferenceResult


@dataclass
class FakeChain:
    config: ChainConfig = field(
        default_factory=lambda: ChainConfig(
            owner="owner.testnet",
            paused=False,
            next_request_id=1,
            request_ttl_ns=600_000_000_000,
            day_ns=86_400_000_000_000,
        )
    )
    requests: dict[int, ChainRequest] = field(default_factory=dict)
    grants: dict[tuple[str, str], ChainGrant] = field(default_factory=dict)
    brokers: dict[str, ChainBroker] = field(default_factory=dict)
    credits: dict[str, int] = field(default_factory=dict)
    receipts: dict[str, list[ChainReceipt]] = field(default_factory=dict)
    rejected_keys: set[tuple[str, str]] = field(default_factory=set)
    failures: dict[str, ContractError] = field(default_factory=dict)
    calls: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    receipts_recorded: list[tuple[int, str]] = field(default_factory=list)
    refunds: list[tuple[int, str]] = field(default_factory=list)
    expired: list[int] = field(default_factory=list)
    closed: bool = False

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))
        failure = self.failures.get(name)
        if failure is not None:
            raise failure

    async def close(self) -> None:
        self.closed = True

    async def get_request(self, req_id: int) -> ChainRequest | None:
        self._record("get_request", req_id)
        return self.requests.get(req_id)

    async def get_grant(self, owner: str, agent: str) -> ChainGrant | None:
        self._record("get_grant", owner, agent)
        return self.grants.get((owner, agent))

    async def get_broker(self, owner: str) -> ChainBroker | None:
        self._record("get_broker", owner)
        return self.brokers.get(owner)

    async def get_config(self) -> ChainConfig:
        self._record("get_config")
        return self.config

    async def credit_of(self, agent: str) -> int:
        self._record("credit_of", agent)
        return self.credits.get(agent, 0)

    async def recent_receipts(self, owner: str, from_: int, limit: int) -> list[ChainReceipt]:
        self._record("recent_receipts", owner, from_, limit)
        items = self.receipts.get(owner, [])
        return items[from_ : from_ + limit]

    async def record_receipt(self, req_id: int, receipt_hash: str) -> str:
        self._record("record_receipt", req_id, receipt_hash)
        request = self.requests.get(req_id)
        if request is not None:
            self.requests[req_id] = replace(request, status="Served", receipt_hash=receipt_hash)
        self.receipts_recorded.append((req_id, receipt_hash))
        return f"receipt-tx-{req_id}"

    async def refund(self, req_id: int, reason: str) -> str:
        self._record("refund", req_id, reason)
        request = self.requests.get(req_id)
        if request is not None:
            self.requests[req_id] = replace(request, status="Refunded")
        self.refunds.append((req_id, reason))
        return f"refund-tx-{req_id}"

    async def expire_request(self, req_id: int) -> str:
        self._record("expire_request", req_id)
        request = self.requests.get(req_id)
        if request is not None:
            self.requests[req_id] = replace(request, status="Expired")
        self.expired.append(req_id)
        return f"expire-tx-{req_id}"

    async def verify_account_key(
        self, account: str, public_key: str, *, require_function_call: bool
    ) -> None:
        self._record("verify_account_key", account, public_key, require_function_call)
        if (account, public_key) in self.rejected_keys:
            raise MnemosError(
                401, E_KEY_NOT_FOUND, "the signing key does not belong to this account"
            )

    async def ping(self) -> None:
        self._record("ping")


@dataclass
class FakeInference:
    answers: list[InferenceResult] = field(default_factory=list)
    error: InferenceError | None = None
    is_ready: bool = True
    prompts: list[tuple[str, str, int]] = field(default_factory=list)
    closed: bool = False

    def queue(self, *answers: str) -> None:
        for answer in answers:
            chat_id = f"chat-{len(self.answers)}"
            self.answers.append(make_inference_result(answer, chat_id=chat_id))

    async def complete(
        self, *, system_prompt: str, user_prompt: str, max_tokens: int
    ) -> InferenceResult:
        self.prompts.append((system_prompt, user_prompt, max_tokens))
        if self.error is not None:
            raise self.error
        if not self.answers:
            raise AssertionError("FakeInference has no queued answer")
        return self.answers.pop(0)

    async def ready(self) -> bool:
        return self.is_ready

    async def close(self) -> None:
        self.closed = True


def make_inference_result(answer: str, *, chat_id: str = "chat-1") -> InferenceResult:
    return InferenceResult(
        answer=answer,
        chat_id=chat_id,
        signing_address="0xsigner",
        signing_algo="ed25519",
        signature_kind="provider_tee",
        attestation={
            "signature_kind": "provider_tee",
            "signer": {"signing_address": "0xsigner", "signing_algo": "ed25519"},
            "tcb_status": "UpToDate",
            "advisory_ids": [],
            "deployment": {
                "app_compose_sha256": "0" * 64,
                "os_image_hash": "os-image",
                "compose_hash": "compose-hash",
                "compose_manager_verified": True,
            },
            "deployment_provenance": "near-ai-cloud",
            "verified_at": "2026-11-11T00:00:00+00:00",
        },
        request_bytes=b'{"messages":"test"}',
        response_bytes=f'{{"content":"{answer}"}}'.encode(),
    )
