"""Strict encodings shared by the API, security and chain layers."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Final

import base58

ACCOUNT_RE: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}[a-z0-9]$")
SCOPE_RE: Final = re.compile(r"^[a-z0-9-]{1,32}$")
HEX64_RE: Final = re.compile(r"^[0-9a-f]{64}$")
ED25519_PREFIX: Final = "ed25519:"


class EncodingError(ValueError):
    """A value did not match the protocol encoding."""


def b64decode_strict(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise EncodingError("value is not valid base64") from error


def b64encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def hex_to_bytes(value: str) -> bytes:
    if len(value) % 2 != 0 or not re.fullmatch(r"[0-9a-f]*", value):
        raise EncodingError("value is not lowercase hex")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise EncodingError("value is not lowercase hex") from error


def bytes_to_hex(value: bytes) -> str:
    return value.hex()


def decode_ed25519_public_key(value: str) -> bytes:
    if not value.startswith(ED25519_PREFIX):
        raise EncodingError("only ed25519 public keys are supported")
    try:
        raw = base58.b58decode(value[len(ED25519_PREFIX) :])
    except ValueError as error:
        raise EncodingError("public key is not valid base58") from error
    if len(raw) != 32:
        raise EncodingError("ed25519 public key must decode to 32 bytes")
    return raw


def validate_account(value: str) -> str:
    if not ACCOUNT_RE.fullmatch(value):
        raise EncodingError("account must be a lowercase NEAR account id")
    return value


def validate_scope(value: str) -> str:
    if not SCOPE_RE.fullmatch(value):
        raise EncodingError("scope must match [a-z0-9-]{1,32}")
    return value


def validate_hash(value: str) -> str:
    if not HEX64_RE.fullmatch(value):
        raise EncodingError("hash must be 64 lowercase hex characters")
    return value
