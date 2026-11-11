"""Test helpers shared by unit and integration tests."""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from mnemos_broker.chain import ChainGrant, ChainRequest
from mnemos_broker.config import Settings
from mnemos_broker.crypto import ItemEnvelope, SealMaterials, seal_item
from mnemos_broker.db import create_session_factory
from mnemos_broker.models import ReadRequest, VaultItem
from mnemos_broker.near.keys import NearKeyPair

OWNER_SALT = b"\x07" * 16
PASSPHRASE = "correct horse battery staple"
RECIPIENT = "localhost:8000"
NEP413_TAG = 2_147_484_061


def broker_public_key(settings: Settings) -> bytes:
    key = X25519PrivateKey.from_private_bytes(settings.broker_private_key)
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def seal(
    settings: Settings,
    *,
    owner: str = "owner.testnet",
    scope: str = "health",
    text: str = "My flight to Lisbon is on 14 March at 09:15.",
    item_id: str | None = None,
    materials: SealMaterials | None = None,
) -> ItemEnvelope:
    return seal_item(
        owner=owner,
        scope=scope,
        item_id=item_id or str(uuid.uuid4()),
        plaintext=text,
        passphrase=PASSPHRASE,
        owner_salt=OWNER_SALT,
        broker_public_key=broker_public_key(settings),
        materials=materials,
    )


def vault_payload(envelope: ItemEnvelope, salt: bytes = OWNER_SALT) -> dict[str, str]:
    return {
        "id": envelope.item_id,
        "scope": envelope.scope,
        "ciphertext_b64": base64.b64encode(envelope.ciphertext).decode(),
        "nonce_b64": base64.b64encode(envelope.nonce).decode(),
        "wrapped_dek_owner_b64": base64.b64encode(envelope.wrapped_dek_owner).decode(),
        "wrapped_dek_broker_b64": base64.b64encode(envelope.wrapped_dek_broker).decode(),
        "content_hash": envelope.content_hash,
        "owner_salt_b64": base64.b64encode(salt).decode(),
    }


def borsh_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "little") + encoded


def nep413_payload(message: str, nonce: bytes, recipient: str) -> bytes:
    return (
        NEP413_TAG.to_bytes(4, "little")
        + borsh_string(message)
        + nonce
        + borsh_string(recipient)
        + b"\x00"
    )


def sign_nep413(key: NearKeyPair, *, message: str, nonce: bytes, recipient: str) -> str:
    digest = hashlib.sha256(nep413_payload(message, nonce, recipient)).digest()
    return base64.b64encode(key.sign(digest)).decode()


def sign_ask(
    key: NearKeyPair,
    *,
    req_id: int,
    question: str,
    nonce_hex: str,
    recipient: str = RECIPIENT,
) -> str:
    message = "|".join(
        [
            "mnemos:v1:ask",
            str(req_id),
            hashlib.sha256(question.encode("utf-8")).hexdigest(),
            nonce_hex,
            recipient,
        ]
    )
    signature = key.sign(hashlib.sha256(message.encode("utf-8")).digest())
    return base64.b64encode(signature).decode()


def question_hash(question: str, nonce_hex: str) -> str:
    return hashlib.sha256(question.encode("utf-8") + bytes.fromhex(nonce_hex)).hexdigest()


def make_request(
    *,
    req_id: int = 1,
    owner: str = "owner.testnet",
    agent: str = "agent.testnet",
    scope: str = "health",
    price: int = 10_000_000_000_000_000_000_000,
    question: str = "When is my flight?",
    nonce_hex: str = "11" * 32,
    status: str = "Approved",
    age_seconds: int = 10,
) -> ChainRequest:
    return ChainRequest(
        req_id=req_id,
        owner=owner,
        agent=agent,
        scope=scope,
        price=price,
        q_hash=question_hash(question, nonce_hex),
        status=status,
        created_ns=time.time_ns() - age_seconds * 1_000_000_000,
        receipt_hash=None,
    )


def make_grant(
    *,
    owner: str = "owner.testnet",
    agent: str = "agent.testnet",
    scopes: tuple[str, ...] = ("health",),
    price: int = 10_000_000_000_000_000_000_000,
    daily_cap: int = 10,
    expires_in_seconds: int = 86_400,
    max_answer_tokens: int = 256,
    revoked: bool = False,
    used_today: int = 0,
) -> ChainGrant:
    remaining = max(0, daily_cap - used_today)
    return ChainGrant(
        owner=owner,
        agent=agent,
        scopes=scopes,
        price=price,
        daily_cap=daily_cap,
        expires_ns=time.time_ns() + expires_in_seconds * 1_000_000_000,
        max_answer_tokens=max_answer_tokens,
        revoked=revoked,
        used_today=used_today,
        remaining_today=remaining,
        day_index=20_000,
    )


def ask_payload(
    key: NearKeyPair,
    *,
    req_id: int = 1,
    question: str = "When is my flight?",
    nonce_hex: str = "11" * 32,
    agent: str = "agent.testnet",
    recipient: str = RECIPIENT,
) -> dict[str, Any]:
    return {
        "req_id": req_id,
        "question": question,
        "nonce": nonce_hex,
        "signature_b64": sign_ask(
            key, req_id=req_id, question=question, nonce_hex=nonce_hex, recipient=recipient
        ),
        "agent": agent,
        "public_key": key.public_key,
    }


async def authenticate(
    client: Any,
    *,
    account: str,
    key: NearKeyPair,
    recipient: str = RECIPIENT,
) -> Any:
    challenge = await client.post("/v1/auth/challenge", json={"account": account})
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    signature = sign_nep413(
        key,
        message=body["message"],
        nonce=bytes.fromhex(body["nonce_hex"]),
        recipient=recipient,
    )
    response = await client.post(
        "/v1/auth/verify",
        json={
            "account": account,
            "nonce_hex": body["nonce_hex"],
            "public_key": key.public_key,
            "signature_b64": signature,
        },
    )
    return response


def utc_now() -> datetime:
    return datetime.now(UTC)


async def insert_vault_item(engine: Any, envelope: ItemEnvelope) -> None:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add(
            VaultItem(
                id=uuid.UUID(envelope.item_id),
                owner=envelope.owner,
                scope=envelope.scope,
                ciphertext=envelope.ciphertext,
                nonce=envelope.nonce,
                wrapped_dek_owner=envelope.wrapped_dek_owner,
                wrapped_dek_broker=envelope.wrapped_dek_broker,
                content_hash=envelope.content_hash,
            )
        )
        await session.commit()


async def insert_read_request(engine: Any, **values: Any) -> None:
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        session.add(ReadRequest(**values))
        await session.commit()
