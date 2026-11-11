"""NEAR ed25519 key handling and NEP-413 message verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import base58
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ED25519_PREFIX = "ed25519:"
NEP413_PREFIX_TAG = 2_147_484_061  # 2**31 + 413


def b58encode(value: bytes) -> str:
    return base58.b58encode(value).decode("ascii")


def b58decode(value: str) -> bytes:
    return base58.b58decode(value)


def fingerprint_hex(public_key: bytes) -> str:
    return hashlib.sha256(public_key).hexdigest()


@dataclass(frozen=True)
class NearKeyPair:
    """An ed25519 key in NEAR's `ed25519:<base58>` representation."""

    private_key: Ed25519PrivateKey
    public_key_bytes: bytes

    @classmethod
    def from_secret_key(cls, secret_key: str) -> NearKeyPair:
        if not secret_key.startswith(ED25519_PREFIX):
            raise ValueError("only ed25519 keys are supported")
        raw = b58decode(secret_key[len(ED25519_PREFIX) :])
        if len(raw) == 64:
            seed, encoded_public = raw[:32], raw[32:]
        elif len(raw) == 32:
            seed, encoded_public = raw, b""
        else:
            raise ValueError("secret key must decode to 32 or 64 bytes")
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
        public_key = public_key_bytes_of(private_key)
        if encoded_public and encoded_public != public_key:
            raise ValueError("secret key contains a mismatched public key")
        return cls(private_key=private_key, public_key_bytes=public_key)

    @property
    def public_key(self) -> str:
        return ED25519_PREFIX + b58encode(self.public_key_bytes)

    def sign(self, message: bytes) -> bytes:
        return self.private_key.sign(message)

    def sign_transaction(self, transaction_bytes: bytes) -> bytes:
        return self.sign(hashlib.sha256(transaction_bytes).digest())

    def sign_nep413(self, message: bytes) -> bytes:
        return self.sign(hashlib.sha256(message).digest())


def public_key_bytes_of(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def decode_public_key(public_key: str) -> bytes:
    if not public_key.startswith(ED25519_PREFIX):
        raise ValueError("only ed25519 public keys are supported")
    raw = b58decode(public_key[len(ED25519_PREFIX) :])
    if len(raw) != 32:
        raise ValueError("ed25519 public key must decode to 32 bytes")
    return raw


def verify_ed25519(public_key: str, signature: bytes, message: bytes) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(decode_public_key(public_key))
        key.verify(signature, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def verify_nep413(
    *,
    public_key: str,
    signature: bytes,
    message: str,
    recipient: str,
    nonce: bytes,
    callback_url: str | None = None,
) -> bool:
    """Verify a NEP-413 signature exactly as the spec defines it."""
    if len(nonce) != 32:
        return False
    payload = (
        NEP413_PREFIX_TAG.to_bytes(4, "little")
        + _borsh_string(message)
        + nonce
        + _borsh_string(recipient)
        + _borsh_option_string(callback_url)
    )
    return verify_ed25519(public_key, signature, hashlib.sha256(payload).digest())


def _borsh_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return len(encoded).to_bytes(4, "little") + encoded


def _borsh_option_string(value: str | None) -> bytes:
    if value is None:
        return b"\x00"
    encoded = value.encode("utf-8")
    return b"\x01" + len(encoded).to_bytes(4, "little") + encoded
