"""extend repository_status with git details (Sprint 2)

Revision ID: 002
Revises: 001
Create Date: 2026-11-05 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("repository_status", sa.Column("branch", sa.String(length=255), nullable=True))
    op.add_column("repository_status", sa.Column("head_sha", sa.String(length=64), nullable=True))
    op.add_column(
        "repository_status",
        sa.Column("head_subject", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "repository_status",
        sa.Column("head_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "repository_status",
        sa.Column("upstream", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "repository_status",
        sa.Column(
            "dirty_conflicted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "repository_status",
        sa.Column(
            "detached",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "repository_status",
        sa.Column(
            "remote_status",
            sa.String(length=32),
            nullable=False,
            server_default="stale",
        ),
    )
    op.add_column("repository_status", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("repository_status", "error")
    op.drop_column("repository_status", "remote_status")
    op.drop_column("repository_status", "detached")
    op.drop_column("repository_status", "dirty_conflicted")
    op.drop_column("repository_status", "upstream")
    op.drop_column("repository_status", "head_date")
    op.drop_column("repository_status", "head_subject")
    op.drop_column("repository_status", "head_sha")
    op.drop_column("repository_status", "branch")
