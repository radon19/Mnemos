from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from mnemos_broker.errors import E_SESSION_EXPIRED, MnemosError
from mnemos_broker.security import (
    CHALLENGE_TTL,
    create_challenge,
    question_digest,
    question_hash,
    sign_session,
    verify_ask_signature,
    verify_owner_nep413,
    verify_session,
)

from .helpers import RECIPIENT, sign_ask, sign_nep413


def test_challenge_is_32_bytes_and_five_minutes() -> None:
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    challenge = create_challenge("owner.testnet", RECIPIENT, now=now)
    assert len(bytes.fromhex(challenge.nonce_hex)) == 32
    assert challenge.expires_at == now + CHALLENGE_TTL
    assert timedelta(minutes=5) == CHALLENGE_TTL
    assert "owner.testnet" in challenge.message
    assert challenge.nonce_hex in challenge.message
    assert RECIPIENT in challenge.message


def test_session_roundtrip_and_expiry() -> None:
    secret = b"s" * 32
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    token, expires = sign_session(
        "owner.testnet", secret, ttl=timedelta(minutes=30), demo=True, now=now
    )
    claims = verify_session(token, secret, now=now + timedelta(minutes=1))
    assert claims.account == "owner.testnet"
    assert claims.demo is True
    assert claims.expires_at == expires
    with pytest.raises(MnemosError) as error:
        verify_session(token, secret, now=expires)
    assert error.value.code == E_SESSION_EXPIRED


def test_session_rejects_tampering_and_malformed_tokens() -> None:
    secret = b"s" * 32
    token, _ = sign_session("owner.testnet", secret, ttl=timedelta(minutes=30))
    encoded, signature = token.split(".", 1)
    flipped = "0" if signature[-1] != "0" else "1"
    tampered = f"{encoded}.{signature[:-1]}{flipped}"
    with pytest.raises(MnemosError):
        verify_session(tampered, secret)
    with pytest.raises(MnemosError):
        verify_session("nonsense", secret)


def test_question_digest_and_hash_are_sha256() -> None:
    import hashlib

    question = "When is my flight?"
    nonce = "ab" * 32
    assert question_digest(question) == hashlib.sha256(question.encode()).hexdigest()
    assert (
        question_hash(question, nonce)
        == hashlib.sha256(question.encode() + bytes.fromhex(nonce)).hexdigest()
    )
    with pytest.raises(ValueError):
        question_hash(question, "00")


def test_question_hash_matches_the_typescript_implementation() -> None:
    """The same vector is pinned in apps/mcp/test/signer.test.ts."""
    assert question_digest("When is my flight?") == (
        "8cb2e018977f5ea40a0701b74a0b2712f8a7e03f82725195f382ce57d8a68b8c"
    )
    assert question_hash("When is my flight?", "11" * 32) == (
        "f3a0b770b51754a113ea2da0a03ffde614b152509db26289a1759759eec2bc71"
    )


def test_ask_signature_verifies_and_rejects_other_message(agent_key) -> None:
    nonce = "11" * 32
    signature = sign_ask(agent_key, req_id=7, question="When is my flight?", nonce_hex=nonce)
    from mnemos_broker.security import build_ask_message

    message = build_ask_message(7, "When is my flight?", nonce, RECIPIENT)
    assert verify_ask_signature(
        public_key=agent_key.public_key, signature_b64=signature, message=message
    )
    assert not verify_ask_signature(
        public_key=agent_key.public_key,
        signature_b64=signature,
        message=build_ask_message(8, "When is my flight?", nonce, RECIPIENT),
    )
    assert not verify_ask_signature(
        public_key=agent_key.public_key, signature_b64="not-base64", message=message
    )


def test_nep413_signature_verifies_with_exact_message(owner_key) -> None:
    nonce = b"\x02" * 32
    message = "Mnemos sign-in\naccount: owner.testnet"
    signature = sign_nep413(owner_key, message=message, nonce=nonce, recipient=RECIPIENT)
    assert verify_owner_nep413(
        public_key=owner_key.public_key,
        signature_b64=signature,
        message=message,
        recipient=RECIPIENT,
        nonce_hex=nonce.hex(),
    )
    assert not verify_owner_nep413(
        public_key=owner_key.public_key,
        signature_b64=signature,
        message=message + " ",
        recipient=RECIPIENT,
        nonce_hex=nonce.hex(),
    )
    assert not verify_owner_nep413(
        public_key=owner_key.public_key,
        signature_b64=signature,
        message=message,
        recipient="other.host",
        nonce_hex=nonce.hex(),
    )
