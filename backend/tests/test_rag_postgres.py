"""PostgreSQL + pgvector RAG integration test (S45-003).

Run with:
    TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db \
        pytest -q tests/test_rag_postgres.py
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from app.config import Settings
from app.db.base import Base
from app.models.entities import Repository
from app.services.code_search_service import CodeSearchService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL.lower().startswith("postgresql"),
    reason="TEST_DATABASE_URL is not a PostgreSQL URL",
)

EMBEDDING_DIMENSIONS = 1536


class FakeEmbeddings:
    """Deterministic embeddings: redis-related text maps to the first axis."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text_value in texts:
            vector = [0.0] * EMBEDDING_DIMENSIONS
            if "redis" in text_value.lower():
                vector[0] = 1.0
            else:
                vector[1] = 1.0
            vectors.append(vector)
        return vectors


def _create_code_chunks_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS code_chunks (
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


@pytest.mark.asyncio
async def test_rag_index_and_search(tmp_path: Path) -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(text(_create_code_chunks_sql()))
            await connection.execute(text("DELETE FROM code_chunks"))
            await connection.execute(text("DELETE FROM repositories"))

        (tmp_path / "redis_config.py").write_text(
            "REDIS_URL = 'redis://localhost:6379/0'\n", encoding="utf-8"
        )
        (tmp_path / "other.py").write_text(
            "print('hello world')\n", encoding="utf-8"
        )

        async with session_factory() as session:
            repository = Repository(path=str(tmp_path.resolve()), tracked=True)
            session.add(repository)
            await session.commit()
            await session.refresh(repository)

        settings = Settings(
            database_url=TEST_DATABASE_URL,
            embedding_model="fake-embed",
            embedding_dimensions=EMBEDDING_DIMENSIONS,
        )
        service = CodeSearchService(
            session_factory,
            settings,
            FakeEmbeddings(),  # type: ignore[arg-type]
            database_url=TEST_DATABASE_URL,
        )

        status = await service.index(force=True)
        assert status.indexed_chunks >= 2, status
        assert status.errors == []

        response = await service.search("redis", limit=5)
        assert response.results, response
        assert response.results[0].path == "redis_config.py"
        assert response.results[0].score > 0.9
        assert response.results[0].url is None
    finally:
        async with session_factory() as session:
            await session.execute(text("DELETE FROM code_chunks"))
            await session.execute(text("DELETE FROM repositories"))
            await session.commit()
        await engine.dispose()
