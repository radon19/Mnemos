from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from mnemos_broker.crypto import (
    MAX_ITEM_BYTES,
    CryptoError,
    ItemEnvelope,
    SealMaterials,
    derive_owner_kek,
    fingerprint_broker_key,
    open_item_with_broker,
    open_item_with_kek,
    open_item_with_owner,
    seal_item,
    seal_item_with_kek,
)

VECTORS_PATH = Path(__file__).resolve().parents[3] / "packages" / "crypto-vectors" / "vectors.json"


def load_vectors() -> dict[str, Any]:
    with VECTORS_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    assert isinstance(data, dict)
    return data


VECTORS = load_vectors()
OWNER: str = VECTORS["owner"]
OWNER_SALT = bytes.fromhex(VECTORS["ownerSalt"])
PASSPHRASE: str = VECTORS["passphrase"]
BROKER_PRIVATE = bytes.fromhex(VECTORS["brokerPrivateKey"])
BROKER_PUBLIC = bytes.fromhex(VECTORS["brokerPublicKey"])
ITEMS: list[dict[str, Any]] = VECTORS["items"]


def envelope_of(item: dict[str, Any]) -> ItemEnvelope:
    expected = item["expected"]
    return ItemEnvelope(
        item_id=item["itemId"],
        owner=OWNER,
        scope=item["scope"],
        ciphertext=bytes.fromhex(expected["ciphertext"]),
        nonce=bytes.fromhex(expected["nonce"]),
        wrapped_dek_owner=bytes.fromhex(expected["wrappedDekOwner"]),
        wrapped_dek_broker=bytes.fromhex(expected["wrappedDekBroker"]),
        content_hash=expected["contentHash"],
    )


def materials_of(item: dict[str, Any]) -> SealMaterials:
    materials = item["materials"]
    return SealMaterials(
        dek=bytes.fromhex(materials["dek"]),
        item_nonce=bytes.fromhex(materials["itemNonce"]),
        owner_wrap_nonce=bytes.fromhex(materials["ownerWrapNonce"]),
        broker_ephemeral_secret=bytes.fromhex(materials["brokerEphemeralSecret"]),
        broker_wrap_nonce=bytes.fromhex(materials["brokerWrapNonce"]),
    )


def expect_code(code: str, action: Any) -> None:
    with pytest.raises(CryptoError) as caught:
        action()
    assert caught.value.code == code, caught.value


def test_fingerprint_is_sha256_of_public_key() -> None:
    assert fingerprint_broker_key(BROKER_PUBLIC) == hashlib.sha256(BROKER_PUBLIC).hexdigest()


@pytest.mark.parametrize("item", ITEMS, ids=[item["itemId"] for item in ITEMS])
def test_reencrypts_vector_byte_for_byte(item: dict[str, Any]) -> None:
    envelope = seal_item(
        owner=OWNER,
        scope=item["scope"],
        item_id=item["itemId"],
        plaintext=item["plaintextUtf8"],
        passphrase=PASSPHRASE,
        owner_salt=OWNER_SALT,
        broker_public_key=BROKER_PUBLIC,
        materials=materials_of(item),
    )
    expected = item["expected"]
    assert envelope.ciphertext.hex() == expected["ciphertext"]
    assert envelope.nonce.hex() == expected["nonce"]
    assert envelope.wrapped_dek_owner.hex() == expected["wrappedDekOwner"]
    assert envelope.wrapped_dek_broker.hex() == expected["wrappedDekBroker"]
    assert envelope.content_hash == expected["contentHash"]


@pytest.mark.parametrize("item", ITEMS, ids=[item["itemId"] for item in ITEMS])
def test_decrypts_vector_as_owner_and_broker(item: dict[str, Any]) -> None:
    envelope = envelope_of(item)
    expected = item["plaintextUtf8"].encode()
    assert (
        open_item_with_owner(envelope=envelope, passphrase=PASSPHRASE, owner_salt=OWNER_SALT)
        == expected
    )
    assert open_item_with_broker(envelope=envelope, broker_private_key=BROKER_PRIVATE) == expected


def test_tamper_detection() -> None:
    envelope = envelope_of(ITEMS[0])
    kek = derive_owner_kek(PASSPHRASE, OWNER_SALT)

    def flip(value: bytes, index: int) -> bytes:
        return value[:index] + bytes([value[index] ^ 1]) + value[index + 1 :]

    cases: list[tuple[str, ItemEnvelope, Any]] = [
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(**{**envelope.__dict__, "ciphertext": flip(envelope.ciphertext, 3)}),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(**{**envelope.__dict__, "scope": "work"}),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(**{**envelope.__dict__, "owner": "mnemos-agent-76badc8e.testnet"}),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(
                **{**envelope.__dict__, "item_id": "00000000-0000-4000-8000-000000000000"}
            ),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(
                **{
                    **envelope.__dict__,
                    "wrapped_dek_owner": flip(envelope.wrapped_dek_owner, 20),
                }
            ),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
        (
            "E_DECRYPT_FAILED",
            ItemEnvelope(
                **{
                    **envelope.__dict__,
                    "wrapped_dek_broker": flip(envelope.wrapped_dek_broker, 50),
                }
            ),
            lambda env: open_item_with_broker(envelope=env, broker_private_key=BROKER_PRIVATE),
        ),
        (
            "E_CONTENT_HASH_MISMATCH",
            ItemEnvelope(**{**envelope.__dict__, "content_hash": "00" * 32}),
            lambda env: open_item_with_kek(envelope=env, kek=kek),
        ),
    ]
    for code, tampered, action in cases:
        expect_code(code, lambda action=action, tampered=tampered: action(tampered))

    expect_code(
        "E_DECRYPT_FAILED",
        lambda: open_item_with_owner(
            envelope=envelope, passphrase="wrong passphrase", owner_salt=OWNER_SALT
        ),
    )
    expect_code(
        "E_DECRYPT_FAILED",
        lambda: open_item_with_owner(
            envelope=envelope, passphrase=PASSPHRASE, owner_salt=b"\x00" * 16
        ),
    )


def test_validation() -> None:
    base: dict[str, Any] = {
        "owner": OWNER,
        "scope": "travel",
        "item_id": "6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
        "plaintext": b"note",
        "kek": b"\x00" * 32,
        "broker_public_key": BROKER_PUBLIC,
    }
    expect_code("E_INVALID_OWNER", lambda: seal_item_with_kek(**{**base, "owner": "BadOwner"}))
    expect_code("E_INVALID_SCOPE", lambda: seal_item_with_kek(**{**base, "scope": "Travel"}))
    expect_code(
        "E_INVALID_ITEM_ID",
        lambda: seal_item_with_kek(**{**base, "item_id": "6F1C2A10-1B2C-4D3E-8F90-0123456789AB"}),
    )
    expect_code("E_EMPTY_ITEM", lambda: seal_item_with_kek(**{**base, "plaintext": b""}))
    expect_code(
        "E_ITEM_TOO_LARGE",
        lambda: seal_item_with_kek(**{**base, "plaintext": b"x" * (MAX_ITEM_BYTES + 1)}),
    )
    expect_code(
        "E_INVALID_KEY",
        lambda: seal_item_with_kek(**{**base, "kek": b"\x00" * 31}),
    )
    expect_code(
        "E_INVALID_PASSPHRASE",
        lambda: derive_owner_kek("", OWNER_SALT),
    )


def test_max_item_size_boundary() -> None:
    envelope = seal_item_with_kek(
        owner=OWNER,
        scope="travel",
        item_id="6f1c2a10-1b2c-4d3e-8f90-0123456789ab",
        plaintext=b"x" * MAX_ITEM_BYTES,
        kek=b"\x00" * 32,
        broker_public_key=BROKER_PUBLIC,
    )
    assert len(envelope.ciphertext) == MAX_ITEM_BYTES + 16
