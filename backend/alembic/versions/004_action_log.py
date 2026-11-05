"""action log

Revision ID: 004
Revises: 003
Create Date: 2026-11-05 15:46:55.128984

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_action_log_created_at"), "action_log", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_action_log_repository_id"),
        "action_log",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_action_log_repository_id"), table_name="action_log")
    op.drop_index(op.f("ix_action_log_created_at"), table_name="action_log")
    op.drop_table("action_log")
