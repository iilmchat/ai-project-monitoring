"""RAG code search unit and SQLite-degradation tests (S44)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from app.config import Settings
from app.models.entities import Repository
from app.services.code_search_service import (
    CodeSearchService,
    RagUnavailableError,
    _chunk_text,
    _is_stale,
    _iter_files,
    _language_for_path,
    _mask_snippet,
)
from app.services.llm_service import LLMService
from app.services.sqlite_vec_store import SqliteVecStore
from fastapi import FastAPI
from httpx import AsyncClient


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "embedding_base_url": "http://127.0.0.1:1234/v1",
        "embedding_model": "test-embed",
        "embedding_dimensions": 3,
        "embedding_allow_remote": False,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_file_walker_ignores_dependencies_and_secrets(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "index.js").write_text("x\n", encoding="utf-8")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "bundle.js").write_text("x\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG")

    files = {
        path.relative_to(tmp_path).as_posix() for path in _iter_files(tmp_path)
    }

    assert files == {"src/app.py", "README.md", "docs/guide.md"}


def test_chunker_preserves_line_ranges_and_overlap() -> None:
    content = "\n".join(f"line {index} " + "x" * 20 for index in range(1, 16))
    chunks = _chunk_text(
        content,
        path="src/app.py",
        language="python",
        max_chars=100,
        overlap=20,
    )

    assert len(chunks) > 1
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == 15
    assert all(chunk.start_line <= chunk.end_line for chunk in chunks)
    assert all(chunk.content for chunk in chunks)
    assert len({chunk.content_hash for chunk in chunks}) == len(chunks)


def test_language_and_snippet_masking() -> None:
    assert _language_for_path(Path("src/app.tsx")) == "tsx"
    assert _language_for_path(Path("README.md")) == "markdown"
    masked = _mask_snippet("password=super-secret\ntoken: abc123\npublic=ok")
    assert "super-secret" not in masked
    assert "abc123" not in masked
    assert "password=****" in masked
    assert "public=ok" in masked


def test_stale_detection() -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    assert _is_stale(None, now) is True
    assert _is_stale(now, now - timedelta(seconds=1)) is False
    assert _is_stale(now, now + timedelta(seconds=1)) is True


def _fake_vectors(texts: list[str]) -> list[list[float]]:
    vectors: list[list[float]] = []
    for text in texts:
        lowered = text.lower()
        if "redis" in lowered:
            vectors.append([1.0, 0.0, 0.0, 0.0])
        elif "postgres" in lowered:
            vectors.append([0.0, 1.0, 0.0, 0.0])
        else:
            vectors.append([0.0, 0.0, 1.0, 0.0])
    return vectors


def _rag_service(
    session_factory: object,
    settings: Settings,
    *,
    vec_store: SqliteVecStore | None = None,
) -> CodeSearchService:
    rag_settings = settings.model_copy(update={"embedding_dimensions": 4})
    service = CodeSearchService(
        session_factory,  # type: ignore[arg-type]
        rag_settings,
        LLMService(rag_settings),
        database_url=rag_settings.database_url,
        vec_store=vec_store,
    )

    async def embed(texts: list[str]) -> list[list[float]]:
        return _fake_vectors(texts)

    service._llm.embed = embed  # type: ignore[method-assign]
    return service


class _PythonFallbackStore(SqliteVecStore):
    """Pretends the C extension failed to load."""

    def __init__(self) -> None:
        self._available = False

    @property
    def available(self) -> bool:
        return False

    def search(self, *args: object, **kwargs: object) -> None:
        return None

    def write(self, records: list[tuple[int, list[float], int, str]]) -> bool:
        return False

    def delete(self, chunk_ids: list[int]) -> bool:
        return False


async def test_sqlite_status_creates_schema(app: FastAPI, client: AsyncClient) -> None:
    status = await client.get("/api/v1/search/code/status")
    assert status.status_code == 200, status.text
    assert status.json()["indexed_chunks"] == 0


async def test_sqlite_search_requires_embedding_model(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    search = await client.post(
        "/api/v1/search/code",
        json={"query": "where is redis configured"},
    )
    assert search.status_code == 503
    assert search.json()["detail"] == "embedding_unavailable"

    index = await client.post("/api/v1/search/code/index", json={})
    assert index.status_code == 202
    assert index.json()["status"] == "started"


async def test_sqlite_vec_store_roundtrip(settings: Settings) -> None:
    pytest.importorskip("sqlite_vec")
    store = SqliteVecStore(settings.database_url, 4)
    assert store.available is True
    assert store.write(
        [
            (1, [1.0, 0.0, 0.0, 0.0], 10, "python"),
            (2, [0.0, 1.0, 0.0, 0.0], 10, "python"),
            (3, [0.9, 0.1, 0.0, 0.0], 20, "ts"),
        ]
    )
    assert store.search([1.0, 0.0, 0.0, 0.0], 1) == [(1, 0.0)]
    filtered = store.search([1.0, 0.0, 0.0, 0.0], 2, [20])
    assert filtered and filtered[0][0] == 3
    by_language = store.search([1.0, 0.0, 0.0, 0.0], 3, None, "python")
    assert by_language and {rowid for rowid, _ in by_language} == {1, 2}
    assert store.delete([1, 2, 3]) is True


async def test_sqlite_index_and_search_use_vector_store(
    session_factory,
    settings: Settings,
    make_repo,
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "rag")
    (repo / "cache.py").write_text("redis client setup\n", encoding="utf-8")
    (repo / "db.py").write_text("postgres connection pool\n", encoding="utf-8")
    async with session_factory() as session:
        session.add(Repository(path=str(repo.resolve()), tracked=True))
        await session.commit()

    service = _rag_service(session_factory, settings)
    assert service.available is True
    assert service._vec.available is True

    status = await service.index()
    assert status.indexed_chunks > 0

    response = await service.search("redis configuration", limit=5, min_score=0.1)
    assert response.indexed_repositories == 1
    assert response.results
    assert response.results[0].path == "cache.py"
    assert response.results[0].score > 0.9

    filtered = await service.search(
        "redis configuration",
        limit=5,
        min_score=0.1,
        language="python",
    )
    assert filtered.results
    assert filtered.results[0].path == "cache.py"


async def test_sqlite_python_fallback_finds_chunks(
    session_factory,
    settings: Settings,
    make_repo,
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "fallback")
    (repo / "cache.py").write_text("redis client setup\n", encoding="utf-8")
    async with session_factory() as session:
        session.add(Repository(path=str(repo.resolve()), tracked=True))
        await session.commit()

    service = _rag_service(
        session_factory,
        settings,
        vec_store=_PythonFallbackStore(),
    )
    await service.index()

    response = await service.search("redis configuration", limit=5, min_score=0.1)
    assert response.results
    assert response.results[0].path == "cache.py"
    assert response.results[0].score > 0.9


async def test_service_accepts_sqlite(
    session_factory,
    settings: Settings,
) -> None:
    service = CodeSearchService(
        session_factory,
        settings,
        LLMService(settings),
        database_url="sqlite+aiosqlite:///./test.db",
    )
    assert service.available is True
    with pytest.raises(RagUnavailableError):
        await service.search("redis")


async def test_llm_embed_returns_vectors_and_blocks_remote() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2, 0.3]},
                    {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                ]
            },
        )

    service = LLMService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )
    vectors = await service.embed(["redis", "postgres"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    blocked = LLMService(
        _settings(embedding_base_url="https://api.example.com/v1"),
        transport=httpx.MockTransport(handler),
    )
    assert await blocked.embed(["redis"]) is None
