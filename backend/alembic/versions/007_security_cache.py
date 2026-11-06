"""security cache

Revision ID: 007
Revises: 006
Create Date: 2026-11-06 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "security_cache",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("ecosystem", sa.String(length=16), nullable=False),
        sa.Column("package", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        op.f("ix_security_cache_checked_at"),
        "security_cache",
        ["checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_security_cache_checked_at"), table_name="security_cache")
    op.drop_table("security_cache")
