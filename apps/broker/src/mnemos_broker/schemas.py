"""Request and response schemas for the public broker API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .crypto import MAX_ITEM_BYTES, NONCE_BYTES, OWNER_SALT_BYTES, X25519_KEY_BYTES
from .encoding import (
    EncodingError,
    b64decode_strict,
    decode_ed25519_public_key,
    validate_account,
    validate_hash,
    validate_scope,
)

MAX_QUESTION_CHARS: Final = 2000


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


def _check_b64(value: str, *, exact: int | None = None, maximum: int | None = None) -> str:
    try:
        raw = b64decode_strict(value)
    except EncodingError as error:
        raise ValueError(str(error)) from error
    if exact is not None and len(raw) != exact:
        raise ValueError(f"decoded value must be {exact} bytes")
    if maximum is not None and len(raw) > maximum:
        raise ValueError(f"decoded value must be at most {maximum} bytes")
    return value


class ChallengeRequest(StrictModel):
    account: str

    @field_validator("account")
    @classmethod
    def _account(cls, value: str) -> str:
        return validate_account(value)


class ChallengeResponse(StrictModel):
    nonce_hex: str
    nonce_b64: str
    message: str
    recipient: str
    expires_at: datetime


class ChallengeVerifyRequest(StrictModel):
    account: str
    nonce_hex: str
    public_key: str
    signature_b64: str

    @field_validator("account")
    @classmethod
    def _account(cls, value: str) -> str:
        return validate_account(value)

    @field_validator("nonce_hex")
    @classmethod
    def _nonce(cls, value: str) -> str:
        return validate_hash(value)

    @field_validator("public_key")
    @classmethod
    def _public_key(cls, value: str) -> str:
        try:
            decode_ed25519_public_key(value)
        except EncodingError as error:
            raise ValueError(str(error)) from error
        return value

    @field_validator("signature_b64")
    @classmethod
    def _signature(cls, value: str) -> str:
        return _check_b64(value, exact=64)


class SessionResponse(StrictModel):
    account: str
    expires_at: datetime
    demo: bool = False


class BrokerPubkeyResponse(StrictModel):
    account: str
    public_key_b64: str
    fingerprint: str
    recipient: str
    network: str
    contract_id: str


class VaultItemCreate(StrictModel):
    id: uuid.UUID
    scope: str
    ciphertext_b64: str
    nonce_b64: str
    wrapped_dek_owner_b64: str
    wrapped_dek_broker_b64: str
    content_hash: str
    owner_salt_b64: str

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: str) -> str:
        return validate_scope(value)

    @field_validator("content_hash")
    @classmethod
    def _hash(cls, value: str) -> str:
        return validate_hash(value)

    @field_validator("ciphertext_b64")
    @classmethod
    def _ciphertext(cls, value: str) -> str:
        return _check_b64(value, maximum=MAX_ITEM_BYTES + 16)

    @field_validator("nonce_b64")
    @classmethod
    def _nonce(cls, value: str) -> str:
        return _check_b64(value, exact=NONCE_BYTES)

    @field_validator("wrapped_dek_owner_b64")
    @classmethod
    def _owner_wrap(cls, value: str) -> str:
        return _check_b64(value, exact=NONCE_BYTES + 32 + 16)

    @field_validator("wrapped_dek_broker_b64")
    @classmethod
    def _broker_wrap(cls, value: str) -> str:
        return _check_b64(value, exact=X25519_KEY_BYTES + NONCE_BYTES + 32 + 16)

    @field_validator("owner_salt_b64")
    @classmethod
    def _owner_salt(cls, value: str) -> str:
        return _check_b64(value, exact=OWNER_SALT_BYTES)

    @model_validator(mode="after")
    def _non_empty(self) -> VaultItemCreate:
        if len(b64decode_strict(self.ciphertext_b64)) <= 16:
            raise ValueError("ciphertext must contain more than a GCM tag")
        return self


class VaultItemView(StrictModel):
    id: uuid.UUID
    scope: str
    ciphertext_b64: str
    nonce_b64: str
    wrapped_dek_owner_b64: str
    content_hash: str
    created_at: datetime


class VaultItemPage(StrictModel):
    items: list[VaultItemView]
    next_cursor: str | None


class OwnerSaltResponse(StrictModel):
    owner_salt_b64: str


class AskRequest(StrictModel):
    req_id: int = Field(ge=1, le=2**63 - 1)
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    nonce: str
    signature_b64: str
    agent: str
    public_key: str

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value

    @field_validator("nonce")
    @classmethod
    def _nonce(cls, value: str) -> str:
        return validate_hash(value)

    @field_validator("agent")
    @classmethod
    def _agent(cls, value: str) -> str:
        return validate_account(value)

    @field_validator("public_key")
    @classmethod
    def _public_key(cls, value: str) -> str:
        try:
            decode_ed25519_public_key(value)
        except EncodingError as error:
            raise ValueError(str(error)) from error
        return value

    @field_validator("signature_b64")
    @classmethod
    def _signature(cls, value: str) -> str:
        return _check_b64(value, exact=64)


class AskResponse(StrictModel):
    req_id: int
    status: Literal["served", "withheld"]
    answer: str | None
    answer_withheld: bool
    verified: bool
    attestation_summary: dict[str, Any] | None
    receipt_hash: str | None
    tx_hash: str | None
    refund_tx_hash: str | None = None
    error_code: str | None = None
    latency_ms: int


class ActivityItem(StrictModel):
    req_id: int
    agent: str
    scope: str
    price: str
    status: str
    source: Literal["broker", "chain"]
    created_at: datetime | None = None
    served_at: datetime | None = None
    receipt_hash: str | None = None
    receipt_tx_hash: str | None = None
    refund_tx_hash: str | None = None
    chat_id: str | None = None
    attestation: dict[str, Any] | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class ActivityPage(StrictModel):
    items: list[ActivityItem]
    next_cursor: str | None


class RedteamRequest(StrictModel):
    scope: str
    max_tokens: int | None = Field(default=None, ge=16, le=8192)

    @field_validator("scope")
    @classmethod
    def _scope(cls, value: str) -> str:
        return validate_scope(value)


class RedteamAttackResult(StrictModel):
    id: str
    label: str
    question: str
    outcome: Literal["blocked", "withheld", "refused", "residual", "passed"]
    reason: str
    answer_preview: str | None


class RedteamReport(StrictModel):
    simulated: bool = True
    scope: str
    model: str
    items_considered: int
    attacks: list[RedteamAttackResult]
    note: str
