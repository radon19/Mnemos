"""Broker persistence models.

The tables mirror BUILD_BRIEF section 7 with two additions that the product
needs: ``owner_accounts`` stores the per-owner PBKDF2 salt, and read requests
carry the settlement transaction hashes so the activity screen can link to the
explorer. No plaintext memory, question text or answer text is ever stored.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from .db import Base

# NEAR prices are u128 yoctoNEAR. The widest legal price is 1000 NEAR, which is
# 10^24 yoctoNEAR and does not fit in a signed 64-bit integer, so the column is
# a numeric(78, 0) and the Python side keeps exact integers.
MAX_YOCTO_DIGITS = 39


class YoctoAmount(TypeDecorator[int]):
    """Exact unsigned yoctoNEAR amount stored as numeric(78, 0)."""

    impl = Numeric(78, 0)
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Any) -> Decimal | None:
        if value is None:
            return None
        if value < 0:
            raise ValueError("a yocto amount cannot be negative")
        return Decimal(value)

    def process_result_value(self, value: Decimal | None, dialect: Any) -> int | None:
        if value is None:
            return None
        return int(value)


def utcnow() -> datetime:
    return datetime.now(UTC)


class OwnerAccount(Base):
    __tablename__ = "owner_accounts"

    account: Mapped[str] = mapped_column(String(64), primary_key=True)
    kdf_salt: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VaultItem(Base):
    __tablename__ = "vault_items"
    __table_args__ = (
        Index("ix_vault_items_owner_scope", "owner", "scope"),
        Index("ix_vault_items_owner_created", "owner", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    wrapped_dek_owner: Mapped[bytes] = mapped_column(LargeBinary(60), nullable=False)
    wrapped_dek_broker: Mapped[bytes] = mapped_column(LargeBinary(92), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReadRequest(Base):
    __tablename__ = "read_requests"
    __table_args__ = (
        Index("ix_read_requests_owner_created", "owner", "created_at"),
        Index("ix_read_requests_status_created", "status", "created_at"),
        Index("ix_read_requests_agent", "agent"),
    )

    req_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    owner: Mapped[str] = mapped_column(String(64), nullable=False)
    agent: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    q_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[int] = mapped_column(YoctoAmount, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="processing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    served_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    refund_tx_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    attestation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuthChallenge(Base):
    __tablename__ = "auth_challenges"
    __table_args__ = (Index("ix_auth_challenges_account", "account"),)

    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    account: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditEvent(Base):
    """Small append-only trail for auth and settlement failures.

    This is intentionally not an activity feed for reads; served reads live in
    ``read_requests`` and on chain. Audit rows contain identifiers and codes
    only, never payloads.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
