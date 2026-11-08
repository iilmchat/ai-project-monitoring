"""RAG code search unit and SQLite-degradation tests (S44)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from app.config import Settings
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


async def test_sqlite_search_and_index_are_unavailable(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    search = await client.post(
        "/api/v1/search/code",
        json={"query": "where is redis configured"},
    )
    assert search.status_code == 503
    assert search.json()["detail"] == "rag_unavailable"

    index = await client.post("/api/v1/search/code/index", json={})
    assert index.status_code == 503
    assert index.json()["detail"] == "rag_unavailable"

    status = await client.get("/api/v1/search/code/status")
    assert status.status_code == 503
    assert status.json()["detail"] == "rag_unavailable"


async def test_service_raises_on_sqlite(
    session_factory,
    settings: Settings,
) -> None:
    service = CodeSearchService(
        session_factory,
        settings,
        LLMService(settings),
        database_url="sqlite+aiosqlite:///./test.db",
    )
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
