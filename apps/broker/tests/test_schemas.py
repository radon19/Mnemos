from __future__ import annotations

import base64
import uuid

import pytest
from pydantic import ValidationError

from mnemos_broker.schemas import AskRequest, RedteamRequest, VaultItemCreate


def vault_values() -> dict[str, str]:
    return {
        "id": str(uuid.uuid4()),
        "scope": "health",
        "ciphertext_b64": base64.b64encode(b"x" * 32).decode(),
        "nonce_b64": base64.b64encode(b"n" * 12).decode(),
        "wrapped_dek_owner_b64": base64.b64encode(b"o" * 60).decode(),
        "wrapped_dek_broker_b64": base64.b64encode(b"b" * 92).decode(),
        "content_hash": "a" * 64,
        "owner_salt_b64": base64.b64encode(b"s" * 16).decode(),
    }


def test_valid_vault_item_is_accepted() -> None:
    parsed = VaultItemCreate(**vault_values())
    assert parsed.scope == "health"
    assert len(parsed.content_hash) == 64


def test_vault_item_rejects_bad_hash() -> None:
    values = vault_values()
    values["content_hash"] = "A" * 64
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_vault_item_rejects_wrong_nonce_size() -> None:
    values = vault_values()
    values["nonce_b64"] = base64.b64encode(b"n" * 11).decode()
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_vault_item_rejects_empty_ciphertext_body() -> None:
    values = vault_values()
    values["ciphertext_b64"] = base64.b64encode(b"x" * 16).decode()
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_vault_item_rejects_extra_fields() -> None:
    values: dict[str, str] = vault_values()
    values["owner"] = "attacker.testnet"
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_vault_item_rejects_bad_scope() -> None:
    values = vault_values()
    values["scope"] = "Health"
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_vault_item_rejects_bad_owner_salt_size() -> None:
    values = vault_values()
    values["owner_salt_b64"] = base64.b64encode(b"s" * 15).decode()
    with pytest.raises(ValidationError):
        VaultItemCreate(**values)


def test_ask_request_valid(agent_key) -> None:
    parsed = AskRequest(
        req_id=1,
        question="When is my flight?",
        nonce="11" * 32,
        signature_b64=base64.b64encode(b"s" * 64).decode(),
        agent="agent.testnet",
        public_key=agent_key.public_key,
    )
    assert parsed.req_id == 1


def test_ask_request_rejects_blank_question(agent_key) -> None:
    with pytest.raises(ValidationError):
        AskRequest(
            req_id=1,
            question="   ",
            nonce="11" * 32,
            signature_b64=base64.b64encode(b"s" * 64).decode(),
            agent="agent.testnet",
            public_key=agent_key.public_key,
        )


def test_ask_request_rejects_oversized_question(agent_key) -> None:
    with pytest.raises(ValidationError):
        AskRequest(
            req_id=1,
            question="q" * 2001,
            nonce="11" * 32,
            signature_b64=base64.b64encode(b"s" * 64).decode(),
            agent="agent.testnet",
            public_key=agent_key.public_key,
        )


def test_ask_request_rejects_short_nonce(agent_key) -> None:
    with pytest.raises(ValidationError):
        AskRequest(
            req_id=1,
            question="q",
            nonce="11" * 31,
            signature_b64=base64.b64encode(b"s" * 64).decode(),
            agent="agent.testnet",
            public_key=agent_key.public_key,
        )


def test_ask_request_rejects_bad_public_key() -> None:
    with pytest.raises(ValidationError):
        AskRequest(
            req_id=1,
            question="q",
            nonce="11" * 32,
            signature_b64=base64.b64encode(b"s" * 64).decode(),
            agent="agent.testnet",
            public_key="secp256k1:abc",
        )


def test_redteam_bounds() -> None:
    assert RedteamRequest(scope="health").max_tokens is None
    with pytest.raises(ValidationError):
        RedteamRequest(scope="health", max_tokens=15)
    with pytest.raises(ValidationError):
        RedteamRequest(scope="health", max_tokens=8193)
