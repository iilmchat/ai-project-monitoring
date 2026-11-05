"""mirror tables

Revision ID: 003
Revises: 002
Create Date: 2026-11-05 15:14:36.276371

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repository_mirror_status",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("github_head_sha", sa.String(length=64), nullable=True),
        sa.Column("gitflic_head_sha", sa.String(length=64), nullable=True),
        sa.Column("github_branch", sa.String(length=255), nullable=True),
        sa.Column("gitflic_branch", sa.String(length=255), nullable=True),
        sa.Column("github_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gitflic_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "mirror_status",
            sa.String(length=32),
            nullable=False,
            server_default="unavailable",
        ),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_repository_mirror_status_repository_id"),
        "repository_mirror_status",
        ["repository_id"],
        unique=True,
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("repository_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="received",
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_webhook_events_event_type"), "webhook_events", ["event_type"], unique=False
    )
    op.create_index(
        op.f("ix_webhook_events_provider"), "webhook_events", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_webhook_events_received_at"),
        "webhook_events",
        ["received_at"],
        unique=False,
    )

    op.add_column(
        "repositories",
        sa.Column("github_full_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column("gitflic_full_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "canonical_provider",
            sa.String(length=16),
            nullable=False,
            server_default="github",
        ),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "mirror_expected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "repositories",
        sa.Column(
            "mirror_policy",
            sa.String(length=64),
            nullable=False,
            server_default="github_to_gitflic",
        ),
    )
    op.create_index(
        op.f("ix_repositories_gitflic_full_name"),
        "repositories",
        ["gitflic_full_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_repositories_github_full_name"),
        "repositories",
        ["github_full_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_repositories_github_full_name"), table_name="repositories")
    op.drop_index(op.f("ix_repositories_gitflic_full_name"), table_name="repositories")
    op.drop_column("repositories", "mirror_policy")
    op.drop_column("repositories", "mirror_expected")
    op.drop_column("repositories", "canonical_provider")
    op.drop_column("repositories", "gitflic_full_name")
    op.drop_column("repositories", "github_full_name")
    op.drop_index(op.f("ix_webhook_events_received_at"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_provider"), table_name="webhook_events")
    op.drop_index(op.f("ix_webhook_events_event_type"), table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index(
        op.f("ix_repository_mirror_status_repository_id"),
        table_name="repository_mirror_status",
    )
    op.drop_table("repository_mirror_status")
