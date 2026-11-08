"""gigachat provider columns

Revision ID: 010
Revises: 009
Create Date: 2026-11-08 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ai_provider_profiles") as batch:
        batch.add_column(
            sa.Column(
                "provider_type",
                sa.String(length=32),
                nullable=False,
                server_default="openai_compatible",
            )
        )
        batch.add_column(
            sa.Column(
                "auth_type",
                sa.String(length=16),
                nullable=False,
                server_default="api_key",
            )
        )
        batch.add_column(sa.Column("client_id", sa.String(length=255), nullable=True))
        batch.add_column(
            sa.Column("client_secret", sa.String(length=2048), nullable=True)
        )
        batch.add_column(sa.Column("oauth_scope", sa.String(length=128), nullable=True))
        batch.add_column(
            sa.Column(
                "oauth_expires_at", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch.add_column(sa.Column("access_token", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ai_provider_profiles") as batch:
        batch.drop_column("access_token")
        batch.drop_column("oauth_expires_at")
        batch.drop_column("oauth_scope")
        batch.drop_column("client_secret")
        batch.drop_column("client_id")
        batch.drop_column("auth_type")
        batch.drop_column("provider_type")
