"""An owner-authorized expertise sale paid through policy-bound NEAR Intents.

The operator explicitly authorizes this fixed expertise offer with their owner
session. This is a separate mainnet USDC rail; it never invents a testnet NEAR
receipt or borrows the contract grant's price/counter. Agent API grants govern
who may spend. The offer cannot be used to buy the private scope.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from .agent_api import AgentApiClient, AgentApiError
from .errors import MnemosError
from .inference import InferenceError
from .models import CommerceRead
from .pipeline import AskPipeline

PRICE = "10000"  # USDC has six decimals: 0.01 USDC, separate from testnet NEAR.


class CommerceService:
    def __init__(self, pipeline: AskPipeline) -> None:
        self.pipeline = pipeline
        self.settings = pipeline.settings

    def require_config(self) -> None:
        s = self.settings
        if not s.agent_api_enabled or not all(
            (
                s.agent_api_key.get_secret_value(),
                s.agent_api_buyer_id,
                s.agent_api_buyer_grant.get_secret_value(),
                s.agent_api_seller_id,
                s.agent_api_seller_grant.get_secret_value(),
                s.agent_api_buyer_account,
                s.agent_api_seller_account,
                s.agent_api_asset,
            )
        ):
            raise MnemosError(503, "E_AGENT_API_CONFIG", "Run make agent-api-setup on the laptop.")

    def api(self) -> AgentApiClient:
        return AgentApiClient(
            self.settings.agent_api_url, self.settings.agent_api_key.get_secret_value()
        )

    async def status(self) -> dict[str, Any]:
        self.require_config()
        s = self.settings
        async with self.api() as api:
            network = await api.request("GET", "/v1/network")
            if network.get("network") != "mainnet":
                raise AgentApiError("E_AGENT_API_NETWORK")
            balance = await api.request("GET", f"/v1/agents/{s.agent_api_buyer_id}/balances")
            policy = await api.request("GET", f"/v1/agents/{s.agent_api_buyer_id}/policy")
        async with self.pipeline.session_factory() as session:
            rows = (
                await session.scalars(
                    select(CommerceRead)
                    .where(CommerceRead.owner == s.mnemos_owner_account)
                    .order_by(CommerceRead.created_at.desc())
                    .limit(10)
                )
            ).all()
            unfinished = (
                await session.scalars(
                    select(CommerceRead)
                    .where(
                        CommerceRead.owner == s.mnemos_owner_account,
                        CommerceRead.status.not_in(["served", "refunded"]),
                    )
                    .order_by(CommerceRead.created_at.asc())
                    .limit(50)
                )
            ).all()
        return {
            "network": "mainnet",
            "rail": "NEAR Agent API / Confidential Intents",
            "buyer_id": s.agent_api_buyer_id,
            "seller_account": s.agent_api_seller_account,
            "buyer_account": s.agent_api_buyer_account,
            "asset": s.agent_api_asset,
            "price_atomic": PRICE,
            "price_usdc": "0.01",
            "balances": balance,
            "policy": policy,
            "dependency_status": network.get("status"),
            "unfinished": [
                {
                    "read_id": str(row.id),
                    "status": row.status,
                    "payment_operation": row.payment_operation,
                    "refund_operation": row.refund_operation,
                }
                for row in unfinished
            ],
            "reads": [
                {
                    "read_id": str(row.id),
                    "status": row.status,
                    "payment": row.payment,
                    "refund": row.refund,
                    "answer_hash": row.answer_hash,
                    "attestation": row.attestation,
                }
                for row in rows
            ],
        }

    def terms(self) -> dict[str, str]:
        s = self.settings
        return {
            "buyer_id": s.agent_api_buyer_id,
            "seller_id": s.agent_api_seller_id,
            "asset": s.agent_api_asset,
            "amount": PRICE,
            "buyer_account": s.agent_api_buyer_account,
            "seller_account": s.agent_api_seller_account,
        }

    def digest(
        self, owner: str, read_id: uuid.UUID, scope: str, question: str, terms: dict[str, Any]
    ) -> str:
        bound = json.dumps(
            ["mnemos-commerce-v1", owner, str(read_id), scope, question, terms],
            sort_keys=True,
            separators=(",", ":"),
        )
        # Independent of session-cookie rotation. Rotating the broker encryption
        # key already requires rewrapping its encrypted vault.
        return hmac.new(
            self.settings.broker_private_key, bound.encode(), hashlib.sha256
        ).hexdigest()

    @asynccontextmanager
    async def locked(
        self, owner: str, read_id: uuid.UUID
    ) -> AsyncIterator[tuple[AsyncSession, CommerceRead]]:
        # Keep an advisory *transaction* lock on a dedicated connection while
        # separate state commits make each external-effect boundary durable.
        lock_id = int.from_bytes(hashlib.sha256(read_id.bytes).digest()[:8], "big", signed=True)
        async with self.pipeline.session_factory() as lock_session, lock_session.begin():
            acquired = await lock_session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id}
            )
            if not acquired:
                raise MnemosError(
                    409, "E_READ_BUSY", "This read is already running. Wait, then refresh."
                )
            async with self.pipeline.session_factory() as session:
                row = await session.get(CommerceRead, read_id)
                if row is None or row.owner != owner:
                    raise MnemosError(
                        404, "E_READ_NOT_FOUND", "No purchase with this ID belongs to this owner."
                    )
                yield session, row

    @staticmethod
    def transfer_body(row: CommerceRead, *, refund: bool = False) -> dict[str, Any]:
        terms = row.terms
        return {
            "asset": terms["asset"],
            "amount": terms["amount"],
            "recipient": terms["buyer_account" if refund else "seller_account"],
            "reference": f"mnemos-{'refund' if refund else 'read'}:{row.id}",
            "confidential": True,
        }

    async def payment(
        self, session: AsyncSession, row: CommerceRead, api: AgentApiClient, *, refund: bool = False
    ) -> dict[str, Any]:
        body = self.transfer_body(row, refund=refund)
        agent = row.terms["seller_id" if refund else "buyer_id"]
        operation = row.refund_operation if refund else row.payment_operation
        if operation:
            # Status lookup does not require a still-live spending grant.
            return await api.confirm(operation, agent=agent, body=body)

        async def remember(correlation: str) -> None:
            if refund:
                row.refund_operation = correlation
            else:
                row.payment_operation = correlation
            await session.commit()  # before polling, cancellation or grant rotation

        grant = (
            self.settings.agent_api_seller_grant if refund else self.settings.agent_api_buyer_grant
        )
        return await api.pay(
            agent=agent,
            grant=grant.get_secret_value(),
            asset=body["asset"],
            amount=body["amount"],
            recipient=body["recipient"],
            reference=body["reference"],
            on_submitted=remember,
        )

    async def refund(self, *, owner: str, read_id: uuid.UUID) -> dict[str, Any]:
        self.require_config()
        async with self.locked(owner, read_id) as (session, row), self.api() as api:
            if row.status == "served":
                raise MnemosError(
                    409, "E_READ_CONSUMED", "A delivered answer cannot be refunded here."
                )
            if row.status == "refunded":
                return {"read_id": str(read_id), "status": row.status, "refund": row.refund}
            if row.payment is None:
                if not row.payment_operation:
                    raise MnemosError(
                        409,
                        "E_PAYMENT_UNKNOWN",
                        "No accepted operation is recorded. Retry the original purchase ID or "
                        "inspect Agent API history; this action never starts a new payment.",
                    )
                try:
                    row.payment = await self.payment(session, row, api)
                    row.status = "paid"
                    await session.commit()
                except AgentApiError as error:
                    raise MnemosError(
                        error.status,
                        error.code,
                        "Payment settlement is unresolved; no new payment was sent.",
                    ) from error
            await self.do_refund(session, row, api)
            return {"read_id": str(read_id), "status": row.status, "refund": row.refund}

    async def do_refund(
        self, session: AsyncSession, row: CommerceRead, api: AgentApiClient
    ) -> None:
        row.status = "refund_pending"
        await session.commit()  # irreversible transition: never go back to inference
        try:
            row.refund = await self.payment(session, row, api, refund=True)
        except AgentApiError as error:
            raise MnemosError(
                502,
                "E_REFUND_PENDING",
                "The answer was not released. Retry the refund by purchase ID.",
                details={"read_id": str(row.id), "refund_status": "PENDING"},
            ) from error
        row.status = "refunded"
        await session.commit()

    async def ask(
        self, *, owner: str, read_id: uuid.UUID, scope: str, question: str
    ) -> dict[str, Any]:
        self.require_config()
        if scope != "expertise":
            raise MnemosError(
                403, "E_SCOPE_DENIED", "This offer permits expertise only. Nothing was charged."
            )
        terms = self.terms()
        async with self.pipeline.session_factory() as session:
            await session.execute(
                insert(CommerceRead)
                .values(
                    id=read_id,
                    owner=owner,
                    terms=terms,
                    request_hash=self.digest(owner, read_id, scope, question, terms),
                    status="pending",
                )
                .on_conflict_do_nothing(index_elements=[CommerceRead.id])
            )
            await session.commit()
        async with self.locked(owner, read_id) as (session, row), self.api() as api:
            if row.status in {"served", "refunded"}:
                raise MnemosError(
                    409, "E_READ_CONSUMED", "This read already finished; it was not charged again."
                )
            if row.status == "refund_pending":
                await self.do_refund(session, row, api)
                raise MnemosError(
                    502,
                    "E_REFUND_RECOVERED",
                    "The earlier failed read has been refunded; no answer was released.",
                    details={"read_id": str(read_id), "refund_status": "SUCCESS"},
                )
            digest = self.digest(owner, read_id, scope, question, row.terms)
            if not hmac.compare_digest(row.request_hash, digest):
                raise MnemosError(
                    409,
                    "E_IDEMPOTENCY_CONFLICT",
                    "This ID belongs to another question. Restore that question or "
                    "recover/refund the payment by ID.",
                )
            if row.payment is None:
                row.status = "paying"
                await session.commit()
                try:
                    row.payment = await self.payment(session, row, api)
                except AgentApiError as error:
                    raise MnemosError(
                        error.status,
                        error.code,
                        "No answer was released. Refresh wallet status and retry "
                        "this same purchase ID.",
                    ) from error
                row.status = "paid"
                await session.commit()
            try:
                outcome = await self.pipeline.answer_scope(
                    owner=owner, scope=scope, question=question
                )
                if outcome["answer"] is None:
                    raise InferenceError("E_OUTPUT_FILTER", "The answer was withheld.")
            except Exception as error:
                code = (
                    error.code
                    if isinstance(error, (InferenceError, MnemosError))
                    else "E_INFERENCE_FAILED"
                )
                await self.do_refund(session, row, api)
                raise MnemosError(
                    502,
                    code,
                    "No answer was released. The payment was refunded.",
                    details={"read_id": str(read_id), "refund_status": "SUCCESS"},
                ) from error
            row.status = "served"
            row.answer_hash = hashlib.sha256(outcome["answer"].encode()).hexdigest()
            row.attestation = outcome["attestation_summary"]
            await session.commit()  # delivery only after durable settlement/delivery state
            return {
                **outcome,
                "read_id": str(read_id),
                "network": "mainnet",
                "price_usdc": "0.01",
                "payment": row.payment,
                "answer_hash": row.answer_hash,
            }
