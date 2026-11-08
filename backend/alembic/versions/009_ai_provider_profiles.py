"""ai provider profiles

Revision ID: 009
Revises: 008
Create Date: 2026-11-08 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen2.5-coder-7b-instruct"


def upgrade() -> None:
    op.create_table(
        "ai_provider_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=False),
        sa.Column("api_key", sa.String(length=2048), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_ai_provider_profiles_is_active"),
        "ai_provider_profiles",
        ["is_active"],
        unique=False,
    )

    bind = op.get_bind()
    settings_table = sa.table(
        "app_settings",
        sa.column("key", sa.String()),
        sa.column("value", sa.Text()),
    )
    stored = {
        row.key: row.value
        for row in bind.execute(sa.select(settings_table)).all()
    }
    base_url = (stored.get("llm_base_url") or DEFAULT_BASE_URL).strip()
    model_name = (stored.get("llm_model") or DEFAULT_MODEL).strip()
    api_key = (stored.get("llm_api_key") or "").strip() or None
    enabled = str(stored.get("llm_enabled") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    lowered = base_url.lower()
    if "11434" in lowered or "ollama" in lowered:
        name = "Local Ollama"
    elif "1234" in lowered or "lmstudio" in lowered:
        name = "Local LM Studio"
    else:
        name = "Default provider"

    profiles_table = sa.table(
        "ai_provider_profiles",
        sa.column("name", sa.String()),
        sa.column("base_url", sa.String()),
        sa.column("api_key", sa.String()),
        sa.column("model_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    bind.execute(
        profiles_table.insert().values(
            name=name,
            base_url=base_url,
            api_key=api_key,
            model_name=model_name,
            is_active=enabled,
            created_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ai_provider_profiles_is_active"),
        table_name="ai_provider_profiles",
    )
    op.drop_table("ai_provider_profiles")
