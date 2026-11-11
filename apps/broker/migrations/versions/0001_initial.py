"""Initial broker schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-11

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "owner_accounts",
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("kdf_salt", sa.LargeBinary(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("account"),
    )

    op.create_table(
        "vault_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(length=12), nullable=False),
        sa.Column("wrapped_dek_owner", sa.LargeBinary(length=60), nullable=False),
        sa.Column("wrapped_dek_broker", sa.LargeBinary(length=92), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vault_items_owner", "vault_items", ["owner"], unique=False)
    op.create_index(
        "ix_vault_items_owner_scope", "vault_items", ["owner", "scope"], unique=False
    )
    op.create_index(
        "ix_vault_items_owner_created", "vault_items", ["owner", "created_at"], unique=False
    )

    op.create_table(
        "read_requests",
        sa.Column("req_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=False),
        sa.Column("agent", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("q_hash", sa.String(length=64), nullable=False),
        sa.Column("price", sa.Numeric(78, 0), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("receipt_hash", sa.String(length=64), nullable=True),
        sa.Column("receipt_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("refund_tx_hash", sa.String(length=128), nullable=True),
        sa.Column("chat_id", sa.String(length=256), nullable=True),
        sa.Column("attestation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("req_id"),
    )
    op.create_index(
        "ix_read_requests_owner_created",
        "read_requests",
        ["owner", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_read_requests_status_created",
        "read_requests",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index("ix_read_requests_agent", "read_requests", ["agent"], unique=False)

    op.create_table(
        "auth_challenges",
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("account", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("nonce"),
    )
    op.create_index(
        "ix_auth_challenges_account", "auth_challenges", ["account"], unique=False
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("subject", sa.String(length=128), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_index("ix_auth_challenges_account", table_name="auth_challenges")
    op.drop_table("auth_challenges")
    op.drop_index("ix_read_requests_agent", table_name="read_requests")
    op.drop_index("ix_read_requests_status_created", table_name="read_requests")
    op.drop_index("ix_read_requests_owner_created", table_name="read_requests")
    op.drop_table("read_requests")
    op.drop_index("ix_vault_items_owner_created", table_name="vault_items")
    op.drop_index("ix_vault_items_owner_scope", table_name="vault_items")
    op.drop_index("ix_vault_items_owner", table_name="vault_items")
    op.drop_table("vault_items")
    op.drop_table("owner_accounts")
