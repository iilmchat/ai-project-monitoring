"""code chunks for sqlite-vec desktop RAG (S61-001)

Revision ID: 015
Revises: 014
Create Date: 2026-11-11 18:00:00.000000

PostgreSQL already owns ``code_chunks`` (revision 011) with a pgvector column.
SQLite needs a plain table: embeddings are stored as JSON text so the pure
Python fallback keeps working when the ``sqlite-vec`` extension is missing.

The ``vec_chunks`` virtual table is created lazily by
``app.services.sqlite_vec_store`` because Alembic's async connection cannot
load the extension synchronously.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS code_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository_id INTEGER NOT NULL REFERENCES repositories(id)
                ON DELETE CASCADE,
            path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            language TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            indexed_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_repository_id "
        "ON code_chunks (repository_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_code_chunks_lookup "
        "ON code_chunks (repository_id, path)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        return
    with suppress(Exception):
        op.execute("DROP TABLE IF EXISTS vec_chunks")
    op.execute("DROP TABLE IF EXISTS code_chunks")
