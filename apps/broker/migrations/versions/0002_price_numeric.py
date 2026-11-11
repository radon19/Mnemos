"""Store read request prices as exact numeric amounts.

Revision ID: 0002_price_numeric
Revises: 0001_initial
Create Date: 2026-11-11

NEAR prices are u128 yoctoNEAR, which does not fit in a signed 64-bit
integer. Databases created from the first draft of 0001 have a bigint price
column; this migration converts them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_price_numeric"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "read_requests",
        "price",
        existing_type=sa.BigInteger(),
        type_=sa.Numeric(78, 0),
        existing_nullable=False,
        postgresql_using="price::numeric(78, 0)",
    )


def downgrade() -> None:
    # A price above the int64 range cannot be represented as bigint again.
    op.alter_column(
        "read_requests",
        "price",
        existing_type=sa.Numeric(78, 0),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="price::bigint",
    )
