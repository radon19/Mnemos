"""Durable idempotency and settlement evidence for Agent API paid answers."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_commerce_reads"
down_revision: str | None = "0002_price_numeric"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_reads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("terms", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payment", postgresql.JSONB(), nullable=True),
        sa.Column("payment_operation", sa.String(128), nullable=True),
        sa.Column("refund", postgresql.JSONB(), nullable=True),
        sa.Column("refund_operation", sa.String(128), nullable=True),
        sa.Column("attestation", postgresql.JSONB(), nullable=True),
        sa.Column("answer_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("commerce_reads")
