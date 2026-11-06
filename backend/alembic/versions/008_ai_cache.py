"""ai cache

Revision ID: 008
Revises: 007
Create Date: 2026-11-06 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_cache",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        op.f("ix_ai_cache_checked_at"),
        "ai_cache",
        ["checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_cache_checked_at"), table_name="ai_cache")
    op.drop_table("ai_cache")
