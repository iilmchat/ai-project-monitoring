"""sast cache

Revision ID: 014
Revises: 013
Create Date: 2026-11-11 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sast_cache",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["repository_id"], ["repositories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        op.f("ix_sast_cache_repository_id"),
        "sast_cache",
        ["repository_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sast_cache_checked_at"),
        "sast_cache",
        ["checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sast_cache_checked_at"), table_name="sast_cache")
    op.drop_index(op.f("ix_sast_cache_repository_id"), table_name="sast_cache")
    op.drop_table("sast_cache")
