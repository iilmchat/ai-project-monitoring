"""separate chat and embedding models for AI provider profiles (v1.4.2)

Revision ID: 016
Revises: 015
Create Date: 2026-11-12 10:00:00.000000

LM Studio (and similar local runtimes) serve the chat model and the embedding
model as two different model ids behind the same OpenAI-compatible endpoint.
Until v1.4.1 the profile stored only ``model_name`` and RAG reused it for
``/v1/embeddings``, which failed with "embedding model is unavailable" when the
chat model had no embedding head.

The new column is nullable. Existing OpenAI-compatible profiles are backfilled
with a local embedding model so RAG keeps working after the upgrade. GigaChat
profiles are left empty: their embedding endpoint is not part of the supported
contract, and the user can explicitly configure one later.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_EMBEDDING_MODEL = "text-embedding-nomic-embed-text-v1.5"


def _has_embedding_model() -> bool:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("ai_provider_profiles")
    }
    return "embedding_model" in columns


def upgrade() -> None:
    # Legacy desktop databases created with ``create_all`` may already have the
    # column while being stamped at revision 015. Keep the migration idempotent.
    if not _has_embedding_model():
        with op.batch_alter_table("ai_provider_profiles") as batch:
            batch.add_column(
                sa.Column("embedding_model", sa.String(length=255), nullable=True)
            )
    op.execute(
        sa.text(
            "UPDATE ai_provider_profiles "
            "SET embedding_model = :model "
            "WHERE embedding_model IS NULL "
            "AND COALESCE(provider_type, 'openai_compatible') != 'gigachat'"
        ).bindparams(model=DEFAULT_EMBEDDING_MODEL)
    )


def downgrade() -> None:
    if not _has_embedding_model():
        return
    with op.batch_alter_table("ai_provider_profiles") as batch:
        batch.drop_column("embedding_model")
