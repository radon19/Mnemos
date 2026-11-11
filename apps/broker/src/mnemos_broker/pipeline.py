"""The ask pipeline: authenticate, claim, decrypt, rank, infer, filter, settle.

Ordering is a security property, not an implementation detail:

1. Verify the agent's signature and on-chain key before touching a request.
2. Verify the request belongs to that agent and that q_hash binds the question
   and nonce.
3. Claim the request with a database primary-key insert, so concurrent calls
   cannot both serve it.
4. Only then start work whose failure warrants a refund.

Failures before the claim (bad signature, wrong agent, wrong q_hash) do not
refund: otherwise an attacker could cancel someone else's pending read.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .activity import ActivityPublisher
from .chain import (
    ChainGrant,
    ChainProtocol,
    ChainRequest,
    ContractError,
    map_contract_error,
)
from .config import Settings
from .crypto import CryptoError, ItemEnvelope, open_item_with_broker
from .errors import (
    E_AGENT_MISMATCH,
    E_GRANT_EXPIRED,
    E_GRANT_NOT_FOUND,
    E_GRANT_REVOKED,
    E_INTERNAL,
    E_ITEM_CORRUPT,
    E_NO_MEMORY,
    E_OUTPUT_FILTER,
    E_PAUSED,
    E_Q_HASH_MISMATCH,
    E_REQUEST_CONSUMED,
    E_REQUEST_EXPIRED,
    E_REQUEST_NOT_APPROVED,
    E_REQUEST_NOT_FOUND,
    E_SCOPE_DENIED,
    MnemosError,
)
from .filter import FilterResult, answer_preview, check_answer
from .inference import (
    InferenceError,
    InferenceProtocol,
    InferenceResult,
    inference_error,
)
from .models import ReadRequest, VaultItem
from .prompts import (
    MemoryItem,
    build_retry_system_prompt,
    build_system_prompt,
    build_user_prompt,
)
from .ranking import rank_items
from .schemas import AskRequest, AskResponse
from .security import (
    build_ask_message,
    question_hash,
    require_ask_signature,
)

logger = logging.getLogger(__name__)

REQUEST_TTL_NS = 600_000_000_000
MAX_CANDIDATE_ITEMS = 500


@dataclass(frozen=True)
class Generation:
    result: InferenceResult
    filter_result: FilterResult
    attempts: int
    withheld: bool


@dataclass(frozen=True)
class SimulationOutcome:
    answer: str | None
    verified: bool
    filter_result: FilterResult
    withheld: bool
    attestation: dict[str, Any]
    latency_ms: int
    items_considered: int
    raw_answer_preview: str
    memories: tuple[str, ...] = ()


class AskPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        chain: ChainProtocol,
        inference: InferenceProtocol,
        publisher: ActivityPublisher,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.chain = chain
        self.inference = inference
        self.publisher = publisher
        self._now = now or (lambda: datetime.now(UTC))

    async def ask(self, body: AskRequest) -> AskResponse:
        started = monotonic()
        now = self._now()
        message = build_ask_message(
            body.req_id, body.question, body.nonce, self.settings.broker_recipient
        )
        require_ask_signature(
            public_key=body.public_key,
            signature_b64=body.signature_b64,
            message=message,
        )
        try:
            await self.chain.verify_account_key(
                body.agent, body.public_key, require_function_call=True
            )
        except ContractError as error:
            raise map_contract_error(error) from error

        request = await self._fetch_request(body.req_id)
        if self._is_expired(request, now):
            await self._expire_stale(request)
            raise MnemosError(
                409,
                E_REQUEST_EXPIRED,
                "the read request has passed its 10-minute window; create a new one",
            )
        self._validate_request(body, request, now)
        await self._claim(request, now)

        try:
            config = await self.chain.get_config()
            if config.paused:
                raise MnemosError(403, E_PAUSED, "the contract is paused")
            grant = await self.chain.get_grant(request.owner, request.agent)
            self._validate_grant(grant, request, now)
            assert grant is not None
            memories = await self._load_memories(request)
            if not memories:
                raise MnemosError(
                    409,
                    E_NO_MEMORY,
                    "no readable memory exists for this scope",
                )
            selected, considered = rank_items(
                body.question, memories, max_answer_tokens=grant.max_answer_tokens
            )
            if not selected:
                raise MnemosError(409, E_NO_MEMORY, "no memory item fits the context budget")
            generation = await self._generate(
                question=body.question,
                items=selected,
                max_answer_tokens=grant.max_answer_tokens,
            )
        except MnemosError as error:
            await self._refund_and_mark(request, error.code, now)
            raise
        except ContractError as error:
            await self._refund_and_mark(request, error.code, now)
            raise map_contract_error(error) from error
        except InferenceError as error:
            await self._refund_and_mark(request, error.code, now)
            raise inference_error(error) from error
        except Exception as error:
            await self._refund_and_mark(request, E_INTERNAL, now)
            raise MnemosError(500, E_INTERNAL, "the read could not be completed") from error

        latency_ms = max(1, int((monotonic() - started) * 1000))
        attestation = dict(generation.result.attestation)
        attestation["filter_retry"] = generation.attempts > 1
        attestation["candidates_considered"] = considered

        if generation.withheld:
            refund_tx = await self._refund_and_mark(
                request, E_OUTPUT_FILTER, now, final_status="withheld"
            )
            return AskResponse(
                req_id=request.req_id,
                status="withheld",
                answer=None,
                answer_withheld=True,
                verified=True,
                attestation_summary=attestation,
                receipt_hash=None,
                tx_hash=None,
                refund_tx_hash=refund_tx,
                error_code=E_OUTPUT_FILTER,
                latency_ms=latency_ms,
            )

        receipt_hash = self._receipt_hash(request.req_id, generation.result)
        try:
            receipt_tx = await self.chain.record_receipt(request.req_id, receipt_hash)
        except ContractError as error:
            refund_tx = await self._refund_and_mark(request, error.code, now)
            raise MnemosError(
                map_contract_error(error).status_code,
                error.code,
                f"receipt settlement failed: {error.message}",
                details={"refund_tx_hash": refund_tx},
            ) from error

        served_at = self._now()
        await self._mark(
            request.req_id,
            status="served",
            served_at=served_at,
            receipt_hash=receipt_hash,
            receipt_tx_hash=receipt_tx,
            chat_id=generation.result.chat_id,
            attestation=attestation,
            latency_ms=latency_ms,
            error_code=None,
        )
        self.publisher.publish(
            request.owner,
            {
                "type": "read_served",
                "req_id": request.req_id,
                "agent": request.agent,
                "scope": request.scope,
                "price": str(request.price),
                "receipt_hash": receipt_hash,
                "verified": True,
                "attestation_summary": attestation,
                "served_at": served_at.isoformat(timespec="seconds"),
            },
        )
        return AskResponse(
            req_id=request.req_id,
            status="served",
            answer=generation.result.answer,
            answer_withheld=False,
            verified=True,
            attestation_summary=attestation,
            receipt_hash=receipt_hash,
            tx_hash=receipt_tx,
            latency_ms=latency_ms,
        )

    async def simulate_one(
        self,
        *,
        owner: str,
        scope: str,
        question: str,
        max_answer_tokens: int = 256,
    ) -> SimulationOutcome:
        started = monotonic()
        memories = await self._load_scope(owner, scope)
        if not memories:
            raise MnemosError(409, E_NO_MEMORY, "no readable memory exists for this scope")
        selected, considered = rank_items(question, memories, max_answer_tokens=max_answer_tokens)
        generation = await self._generate(
            question=question,
            items=selected,
            max_answer_tokens=max_answer_tokens,
        )
        return SimulationOutcome(
            answer=None if generation.withheld else generation.result.answer,
            verified=True,
            filter_result=generation.filter_result,
            withheld=generation.withheld,
            attestation=generation.result.attestation,
            latency_ms=max(1, int((monotonic() - started) * 1000)),
            items_considered=considered,
            raw_answer_preview=answer_preview(generation.result.answer),
            memories=tuple(item.text for item in selected),
        )

    async def _fetch_request(self, req_id: int) -> ChainRequest:
        try:
            request = await self.chain.get_request(req_id)
        except ContractError as error:
            raise map_contract_error(error) from error
        if request is None:
            raise MnemosError(
                404, E_REQUEST_NOT_FOUND, "no such read request; create one on chain first"
            )
        return request

    def _validate_request(self, body: AskRequest, request: ChainRequest, now: datetime) -> None:
        if request.agent != body.agent:
            raise MnemosError(
                403,
                E_AGENT_MISMATCH,
                "the signed agent does not own this read request",
            )
        if request.status == "Served":
            raise MnemosError(409, E_REQUEST_CONSUMED, "this read request was already served")
        if request.status != "Approved":
            raise MnemosError(409, E_REQUEST_NOT_APPROVED, "this read request is not approved")
        if request.q_hash != question_hash(body.question, body.nonce):
            raise MnemosError(
                400,
                E_Q_HASH_MISMATCH,
                "q_hash does not match sha256(question || nonce)",
            )

    def _is_expired(self, request: ChainRequest, now: datetime) -> bool:
        now_ns = int(now.timestamp() * 1_000_000_000)
        return now_ns >= request.created_ns + REQUEST_TTL_NS

    async def _expire_stale(self, request: ChainRequest) -> None:
        try:
            await self.chain.expire_request(request.req_id)
        except ContractError as error:
            logger.info(
                "stale request could not be expired",
                extra={"req_id": request.req_id, "error_code": error.code},
            )

    def _validate_grant(
        self, grant: ChainGrant | None, request: ChainRequest, now: datetime
    ) -> None:
        if grant is None:
            raise MnemosError(404, E_GRANT_NOT_FOUND, "the grant no longer exists")
        if grant.revoked:
            raise MnemosError(403, E_GRANT_REVOKED, "the grant has been revoked")
        if int(now.timestamp() * 1_000_000_000) >= grant.expires_ns:
            raise MnemosError(403, E_GRANT_EXPIRED, "the grant has expired")
        if request.scope not in grant.scopes:
            raise MnemosError(403, E_SCOPE_DENIED, "the request scope is not included in the grant")

    async def _claim(self, request: ChainRequest, now: datetime) -> None:
        record = ReadRequest(
            req_id=request.req_id,
            owner=request.owner,
            agent=request.agent,
            scope=request.scope,
            q_hash=request.q_hash,
            price=request.price,
            status="processing",
            created_at=now,
        )
        async with self.session_factory() as session:
            session.add(record)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise MnemosError(
                    409,
                    E_REQUEST_CONSUMED,
                    "this read request is already being served or was served",
                ) from error
            except Exception as error:
                # The request was paid for on chain but the broker cannot
                # record it. The agent must not pay for the broker's failure,
                # so the credit goes back before the error is reported.
                await session.rollback()
                await self._refund_on_chain(request, E_INTERNAL)
                raise MnemosError(
                    500,
                    E_INTERNAL,
                    "the read could not be recorded, the agent was refunded",
                ) from error

    async def _refund_on_chain(self, request: ChainRequest, code: str) -> str | None:
        try:
            return await self.chain.refund(request.req_id, code[:200])
        except ContractError as error:
            logger.warning(
                "refund failed after an internal error",
                extra={"req_id": request.req_id, "error_code": error.code},
            )
            return None

    async def _load_memories(self, request: ChainRequest) -> list[MemoryItem]:
        return await self._load_scope(request.owner, request.scope)

    async def _load_scope(self, owner: str, scope: str) -> list[MemoryItem]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(VaultItem)
                    .where(
                        VaultItem.owner == owner,
                        VaultItem.scope == scope,
                        VaultItem.deleted_at.is_(None),
                    )
                    .order_by(VaultItem.created_at.desc())
                    .limit(MAX_CANDIDATE_ITEMS)
                )
            ).all()
        items: list[MemoryItem] = []
        for row in rows:
            envelope = ItemEnvelope(
                item_id=str(row.id),
                owner=row.owner,
                scope=row.scope,
                ciphertext=row.ciphertext,
                nonce=row.nonce,
                wrapped_dek_owner=row.wrapped_dek_owner,
                wrapped_dek_broker=row.wrapped_dek_broker,
                content_hash=row.content_hash,
            )
            try:
                plaintext = open_item_with_broker(
                    envelope=envelope,
                    broker_private_key=self.settings.broker_private_key,
                )
                text = plaintext.decode("utf-8")
            except (CryptoError, UnicodeDecodeError) as error:
                code = getattr(error, "code", "E_ITEM_CORRUPT")
                logger.warning(
                    "vault item skipped",
                    extra={"item_id": envelope.item_id, "error_code": code},
                )
                continue
            items.append(
                MemoryItem(
                    item_id=envelope.item_id,
                    scope=row.scope,
                    created_at=row.created_at,
                    text=text,
                )
            )
        if not items and rows:
            raise MnemosError(409, E_ITEM_CORRUPT, "no vault item in this scope could be decrypted")
        return items

    async def _generate(
        self,
        *,
        question: str,
        items: list[MemoryItem],
        max_answer_tokens: int,
    ) -> Generation:
        memories = [item.text for item in items]
        system_prompt = build_system_prompt(max_answer_tokens)
        user_prompt = build_user_prompt(question, items)
        first = await self.inference.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_answer_tokens,
        )
        first_check = check_answer(first.answer, memories)
        if not first_check.leaked:
            return Generation(result=first, filter_result=first_check, attempts=1, withheld=False)

        retry = await self.inference.complete(
            system_prompt=build_retry_system_prompt(max_answer_tokens),
            user_prompt=user_prompt,
            max_tokens=max_answer_tokens,
        )
        retry_check = check_answer(retry.answer, memories)
        return Generation(
            result=retry,
            filter_result=retry_check,
            attempts=2,
            withheld=retry_check.leaked,
        )

    def _receipt_hash(self, req_id: int, result: InferenceResult) -> str:
        request_hash = hashlib.sha256(result.request_bytes).hexdigest()
        response_hash = hashlib.sha256(result.response_bytes).hexdigest()
        material = (
            f"{req_id}|{result.chat_id}|{request_hash}|{response_hash}|{result.signing_address}"
        )
        return hashlib.sha256(material.encode("ascii")).hexdigest()

    async def _refund_and_mark(
        self,
        request: ChainRequest,
        code: str,
        now: datetime,
        *,
        final_status: str | None = None,
    ) -> str | None:
        refund_tx: str | None = None
        try:
            refund_tx = await self.chain.refund(request.req_id, code[:200])
        except ContractError as error:
            if error.code == E_REQUEST_NOT_FOUND:
                logger.info(
                    "refund skipped: request already settled",
                    extra={"req_id": request.req_id},
                )
            else:
                logger.warning(
                    "refund failed",
                    extra={"req_id": request.req_id, "error_code": error.code},
                )
        status = final_status or ("refunded" if refund_tx else "refund_failed")
        await self._mark(
            request.req_id,
            status=status,
            refund_tx_hash=refund_tx,
            error_code=code,
            latency_ms=None,
        )
        self._publish_refused(request, code)
        return refund_tx

    def _publish_refused(self, request: ChainRequest, code: str) -> None:
        self.publisher.publish(
            request.owner,
            {
                "type": "read_refused",
                "req_id": request.req_id,
                "agent": request.agent,
                "scope": request.scope,
                "error_code": code,
                "at": self._now().isoformat(timespec="seconds"),
            },
        )

    async def _mark(self, req_id: int, **values: Any) -> None:
        async with self.session_factory() as session:
            await session.execute(
                update(ReadRequest).where(ReadRequest.req_id == req_id).values(**values)
            )
            await session.commit()
