"""code chunks for RAG search (PostgreSQL + pgvector only)

Revision ID: 011
Revises: 010
Create Date: 2026-11-08 20:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        # SQLite is the default dev/CI database; RAG degrades to 503.
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        f"""
        CREATE TABLE code_chunks (
            id BIGSERIAL PRIMARY KEY,
            repository_id INTEGER NOT NULL REFERENCES repositories(id)
                ON DELETE CASCADE,
            path TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            language TEXT NOT NULL,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
            embedding_model TEXT NOT NULL,
            indexed_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_code_chunks_file_chunk "
        "ON code_chunks (repository_id, path, chunk_index, content_hash)"
    )
    op.execute(
        "CREATE INDEX ix_code_chunks_repository_id "
        "ON code_chunks (repository_id)"
    )
    op.execute(
        "CREATE INDEX ix_code_chunks_content_hash "
        "ON code_chunks (content_hash)"
    )
    op.execute(
        "CREATE INDEX ix_code_chunks_embedding_hnsw "
        "ON code_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS code_chunks")
