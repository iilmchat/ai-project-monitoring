"""create tables

Revision ID: 001
Revises:
Create Date: 2026-11-05 13:16:16.138508

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=True),
        sa.Column("tracked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repositories_path"), "repositories", ["path"], unique=True)
    op.create_index(op.f("ix_repositories_tracked"), "repositories", ["tracked"], unique=False)

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("roots", sa.JSON(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("found_count", sa.Integer(), nullable=False),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scan_runs_started_at"), "scan_runs", ["started_at"], unique=False)

    op.create_table(
        "repository_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("ahead", sa.Integer(), nullable=False),
        sa.Column("behind", sa.Integer(), nullable=False),
        sa.Column("dirty_modified", sa.Integer(), nullable=False),
        sa.Column("dirty_staged", sa.Integer(), nullable=False),
        sa.Column("dirty_untracked", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repository_status_repository_id"),
        "repository_status",
        ["repository_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_repository_status_repository_id"),
        table_name="repository_status",
    )
    op.drop_table("repository_status")
    op.drop_index(op.f("ix_scan_runs_started_at"), table_name="scan_runs")
    op.drop_table("scan_runs")
    op.drop_index(op.f("ix_repositories_tracked"), table_name="repositories")
    op.drop_index(op.f("ix_repositories_path"), table_name="repositories")
    op.drop_table("repositories")
