"""Mnemos envelope encryption, v1 (Python counterpart of @mnemos/crypto).

Wire formats and AAD strings are pinned by ``packages/crypto-vectors`` and must
stay byte-identical to the TypeScript implementation.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PROTOCOL_VERSION: Final = "mnemos:v1"
PBKDF2_ITERATIONS: Final = 600_000
OWNER_SALT_BYTES: Final = 16
DEK_BYTES: Final = 32
NONCE_BYTES: Final = 12
X25519_KEY_BYTES: Final = 32
MAX_ITEM_BYTES: Final = 16 * 1024
BROKER_WRAP_INFO: Final = b"mnemos:v1:wrap-broker"
GCM_TAG_BYTES: Final = 16

_OWNER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$")
_SCOPE_RE = re.compile(r"^[a-z0-9-]{1,32}$")
_ITEM_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class CryptoError(ValueError):
    """A validation or decryption failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SealMaterials:
    """Explicit randomness for deterministic vector generation and tests."""

    dek: bytes
    item_nonce: bytes
    owner_wrap_nonce: bytes
    broker_ephemeral_secret: bytes
    broker_wrap_nonce: bytes


@dataclass(frozen=True)
class ItemEnvelope:
    item_id: str
    owner: str
    scope: str
    ciphertext: bytes
    nonce: bytes
    wrapped_dek_owner: bytes
    wrapped_dek_broker: bytes
    content_hash: str


def item_aad(owner: str, scope: str, item_id: str) -> bytes:
    return f"{PROTOCOL_VERSION}|{owner}|{scope}|{item_id}".encode()


def owner_wrap_aad(item_id: str) -> bytes:
    return f"{PROTOCOL_VERSION}:wrap-owner|{item_id}".encode()


def broker_wrap_aad(item_id: str) -> bytes:
    return f"{PROTOCOL_VERSION}:wrap-broker|{item_id}".encode()


def assert_valid_owner(owner: str) -> None:
    if not _OWNER_RE.fullmatch(owner):
        raise CryptoError(
            "E_INVALID_OWNER",
            "owner must be a lowercase NEAR account id of 2 to 64 characters",
        )


def assert_valid_scope(scope: str) -> None:
    if not _SCOPE_RE.fullmatch(scope):
        raise CryptoError("E_INVALID_SCOPE", "scope must match [a-z0-9-]{1,32}")


def assert_valid_item_id(item_id: str) -> None:
    if not _ITEM_ID_RE.fullmatch(item_id):
        raise CryptoError("E_INVALID_ITEM_ID", "item id must be a lowercase UUID")


def assert_valid_passphrase(passphrase: str) -> None:
    if not 1 <= len(passphrase) <= 1024:
        raise CryptoError("E_INVALID_PASSPHRASE", "passphrase must be 1 to 1024 characters")


def assert_key_length(name: str, key: bytes, expected: int) -> None:
    if len(key) != expected:
        raise CryptoError("E_INVALID_KEY", f"{name} must be {expected} bytes, got {len(key)}")


def derive_owner_kek(passphrase: str, owner_salt: bytes) -> bytes:
    assert_valid_passphrase(passphrase)
    assert_key_length("owner salt", owner_salt, OWNER_SALT_BYTES)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=DEK_BYTES,
        salt=owner_salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(passphrase.encode())


def fingerprint_broker_key(public_key: bytes) -> str:
    assert_key_length("broker public key", public_key, X25519_KEY_BYTES)
    return hashlib.sha256(public_key).hexdigest()


def seal_item(
    *,
    owner: str,
    scope: str,
    item_id: str,
    plaintext: bytes | str,
    passphrase: str,
    owner_salt: bytes,
    broker_public_key: bytes,
    materials: SealMaterials | None = None,
) -> ItemEnvelope:
    kek = derive_owner_kek(passphrase, owner_salt)
    return seal_item_with_kek(
        owner=owner,
        scope=scope,
        item_id=item_id,
        plaintext=plaintext,
        kek=kek,
        broker_public_key=broker_public_key,
        materials=materials,
    )


def seal_item_with_kek(
    *,
    owner: str,
    scope: str,
    item_id: str,
    plaintext: bytes | str,
    kek: bytes,
    broker_public_key: bytes,
    materials: SealMaterials | None = None,
) -> ItemEnvelope:
    assert_valid_owner(owner)
    assert_valid_scope(scope)
    assert_valid_item_id(item_id)
    assert_key_length("owner KEK", kek, DEK_BYTES)
    assert_key_length("broker public key", broker_public_key, X25519_KEY_BYTES)

    body = plaintext.encode() if isinstance(plaintext, str) else plaintext
    if not body:
        raise CryptoError("E_EMPTY_ITEM", "item content must not be empty")
    if len(body) > MAX_ITEM_BYTES:
        raise CryptoError(
            "E_ITEM_TOO_LARGE", f"item content must be at most {MAX_ITEM_BYTES} bytes"
        )

    if materials is None:
        materials = SealMaterials(
            dek=secrets.token_bytes(DEK_BYTES),
            item_nonce=secrets.token_bytes(NONCE_BYTES),
            owner_wrap_nonce=secrets.token_bytes(NONCE_BYTES),
            broker_ephemeral_secret=secrets.token_bytes(X25519_KEY_BYTES),
            broker_wrap_nonce=secrets.token_bytes(NONCE_BYTES),
        )
    assert_key_length("item DEK", materials.dek, DEK_BYTES)
    assert_key_length("item nonce", materials.item_nonce, NONCE_BYTES)
    assert_key_length("owner wrap nonce", materials.owner_wrap_nonce, NONCE_BYTES)
    assert_key_length(
        "broker ephemeral secret", materials.broker_ephemeral_secret, X25519_KEY_BYTES
    )
    assert_key_length("broker wrap nonce", materials.broker_wrap_nonce, NONCE_BYTES)

    ciphertext = AESGCM(materials.dek).encrypt(
        materials.item_nonce, body, item_aad(owner, scope, item_id)
    )
    wrapped_owner = materials.owner_wrap_nonce + AESGCM(kek).encrypt(
        materials.owner_wrap_nonce, materials.dek, owner_wrap_aad(item_id)
    )

    ephemeral = X25519PrivateKey.from_private_bytes(materials.broker_ephemeral_secret)
    ephemeral_public = ephemeral.public_key().public_bytes_raw()
    shared = ephemeral.exchange(X25519PublicKey.from_public_bytes(broker_public_key))
    broker_kek = HKDF(
        algorithm=hashes.SHA256(),
        length=DEK_BYTES,
        salt=None,
        info=BROKER_WRAP_INFO,
    ).derive(shared)
    wrapped_broker = (
        ephemeral_public
        + materials.broker_wrap_nonce
        + AESGCM(broker_kek).encrypt(
            materials.broker_wrap_nonce, materials.dek, broker_wrap_aad(item_id)
        )
    )

    return ItemEnvelope(
        item_id=item_id,
        owner=owner,
        scope=scope,
        ciphertext=ciphertext,
        nonce=materials.item_nonce,
        wrapped_dek_owner=wrapped_owner,
        wrapped_dek_broker=wrapped_broker,
        content_hash=hashlib.sha256(ciphertext).hexdigest(),
    )


def open_item_with_owner(*, envelope: ItemEnvelope, passphrase: str, owner_salt: bytes) -> bytes:
    kek = derive_owner_kek(passphrase, owner_salt)
    return open_item_with_kek(envelope=envelope, kek=kek)


def open_item_with_kek(*, envelope: ItemEnvelope, kek: bytes) -> bytes:
    assert_key_length("owner KEK", kek, DEK_BYTES)
    dek = unwrap_owner_dek(envelope, kek)
    return decrypt_item(envelope, dek)


def open_item_with_broker(*, envelope: ItemEnvelope, broker_private_key: bytes) -> bytes:
    assert_key_length("broker private key", broker_private_key, X25519_KEY_BYTES)
    dek = unwrap_broker_dek(envelope, broker_private_key)
    return decrypt_item(envelope, dek)


def unwrap_owner_dek(envelope: ItemEnvelope, kek: bytes) -> bytes:
    assert_envelope(envelope)
    if len(envelope.wrapped_dek_owner) != NONCE_BYTES + DEK_BYTES + GCM_TAG_BYTES:
        raise CryptoError("E_INVALID_ENVELOPE", "owner-wrapped DEK has an unexpected length")
    nonce = envelope.wrapped_dek_owner[:NONCE_BYTES]
    sealed = envelope.wrapped_dek_owner[NONCE_BYTES:]
    try:
        return AESGCM(kek).decrypt(nonce, sealed, owner_wrap_aad(envelope.item_id))
    except InvalidTag as error:
        raise CryptoError(
            "E_DECRYPT_FAILED",
            "owner unwrap failed: wrong passphrase or tampered data",
        ) from error


def unwrap_broker_dek(envelope: ItemEnvelope, broker_private_key: bytes) -> bytes:
    assert_envelope(envelope)
    expected = X25519_KEY_BYTES + NONCE_BYTES + DEK_BYTES + GCM_TAG_BYTES
    if len(envelope.wrapped_dek_broker) != expected:
        raise CryptoError("E_INVALID_ENVELOPE", "broker-wrapped DEK has an unexpected length")
    ephemeral_public = envelope.wrapped_dek_broker[:X25519_KEY_BYTES]
    nonce = envelope.wrapped_dek_broker[X25519_KEY_BYTES : X25519_KEY_BYTES + NONCE_BYTES]
    sealed = envelope.wrapped_dek_broker[X25519_KEY_BYTES + NONCE_BYTES :]
    try:
        shared = X25519PrivateKey.from_private_bytes(broker_private_key).exchange(
            X25519PublicKey.from_public_bytes(ephemeral_public)
        )
        broker_kek = HKDF(
            algorithm=hashes.SHA256(),
            length=DEK_BYTES,
            salt=None,
            info=BROKER_WRAP_INFO,
        ).derive(shared)
        return AESGCM(broker_kek).decrypt(nonce, sealed, broker_wrap_aad(envelope.item_id))
    except (InvalidTag, ValueError) as error:
        raise CryptoError(
            "E_DECRYPT_FAILED", "broker unwrap failed: wrong key or tampered data"
        ) from error


def decrypt_item(envelope: ItemEnvelope, dek: bytes) -> bytes:
    assert_envelope(envelope)
    assert_key_length("item DEK", dek, DEK_BYTES)
    if len(envelope.nonce) != NONCE_BYTES:
        raise CryptoError("E_INVALID_ENVELOPE", "item nonce has an unexpected length")
    try:
        plaintext = AESGCM(dek).decrypt(
            envelope.nonce,
            envelope.ciphertext,
            item_aad(envelope.owner, envelope.scope, envelope.item_id),
        )
    except InvalidTag as error:
        raise CryptoError(
            "E_DECRYPT_FAILED",
            "item decryption failed: wrong scope, owner, item id, or tampered data",
        ) from error
    verify_content_hash(envelope)
    return plaintext


def verify_content_hash(envelope: ItemEnvelope) -> None:
    actual = hashlib.sha256(envelope.ciphertext).hexdigest()
    if actual != envelope.content_hash:
        raise CryptoError("E_CONTENT_HASH_MISMATCH", "content hash does not match the ciphertext")


def assert_envelope(envelope: ItemEnvelope) -> None:
    assert_valid_owner(envelope.owner)
    assert_valid_scope(envelope.scope)
    assert_valid_item_id(envelope.item_id)
    if not re.fullmatch(r"[0-9a-f]{64}", envelope.content_hash):
        raise CryptoError("E_INVALID_ENVELOPE", "content hash must be 64 lowercase hex characters")
    if len(envelope.ciphertext) < GCM_TAG_BYTES:
        raise CryptoError("E_INVALID_ENVELOPE", "ciphertext is too short to contain a GCM tag")
