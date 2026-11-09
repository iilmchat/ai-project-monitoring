"""AI conflict resolver and release notes tests (S54)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from app.config import Settings
from app.models.entities import Repository
from app.services.llm_service import LLMService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CONFLICT_FILE = (
    "before\n"
    "<<<<<<< HEAD\n"
    "left\n"
    "=======\n"
    "right\n"
    ">>>>>>> feature\n"
    "after\n"
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_enabled": True,
        "llm_base_url": "http://127.0.0.1:1234/v1",
        "llm_model": "test-model",
        "llm_api_key": "",
        "llm_timeout_seconds": 5,
        "llm_allow_remote": False,
        "ai_conflict_max_blocks": 10,
        "ai_conflict_max_chars": 20000,
        "ai_conflict_max_file_bytes": 1048576,
        "ai_release_notes_max_commits": 500,
        "ai_release_notes_max_chars": 20000,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _chat_response(message: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": message}}]},
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


def _enable_llm(app: FastAPI, **overrides: object) -> None:
    settings = app.state.settings
    settings.llm_enabled = True
    settings.llm_base_url = "http://127.0.0.1:1234/v1"
    settings.llm_model = "test-model"
    settings.llm_allow_remote = False
    for key, value in overrides.items():
        setattr(settings, key, value)


@pytest.mark.asyncio
async def test_resolve_conflict_returns_code_and_keeps_file(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "conflict")
    (repo / "app.py").write_text(CONFLICT_FILE, encoding="utf-8", newline="")
    repository_id = await _create_repository(session_factory, repo)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert "<<<<<<<" in request.read().decode("utf-8")
        return _chat_response("left+right")

    _enable_llm(app)
    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    first = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/resolve-conflict",
        json={"file_path": "app.py", "language": "ru"},
    )
    second = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/resolve-conflict",
        json={"file_path": "app.py", "language": "ru"},
    )

    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["resolved"] == "before\nleft+right\nafter\n"
    assert payload["blocks"] == 1
    assert payload["cached"] is False
    assert "verify_before_apply" in payload["warnings"]
    assert first.headers["X-AI-Cache"] == "miss"
    assert second.json()["cached"] is True
    assert second.headers["X-AI-Cache"] == "hit"
    assert calls == 1

    # Read-only: the working tree still contains the original markers.
    assert (repo / "app.py").read_text(encoding="utf-8") == CONFLICT_FILE


@pytest.mark.asyncio
async def test_resolve_conflict_rejects_traversal(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "traversal")
    (repo / "app.py").write_text(CONFLICT_FILE, encoding="utf-8", newline="")
    (tmp_path / "outside.py").write_text(CONFLICT_FILE, encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    app.state.llm_service = LLMService(app.state.settings)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/resolve-conflict",
        json={"file_path": "../outside.py"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "path_outside_repository"


@pytest.mark.asyncio
async def test_resolve_conflict_requires_markers(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "clean")
    (repo / "app.py").write_text("clean\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    app.state.llm_service = LLMService(app.state.settings)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/resolve-conflict",
        json={"file_path": "app.py"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Конфликтов не найдено"


@pytest.mark.asyncio
async def test_resolve_conflict_llm_disabled(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "disabled")
    (repo / "app.py").write_text(CONFLICT_FILE, encoding="utf-8", newline="")
    repository_id = await _create_repository(session_factory, repo)
    app.state.llm_service = LLMService(_settings(llm_enabled=False))

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/resolve-conflict",
        json={"file_path": "app.py"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "llm_disabled"


@pytest.mark.asyncio
async def test_release_notes_success_and_tags(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "release")
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: initial")
    _git(repo, "tag", "v1.0.0")
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: second")
    _git(repo, "tag", "v1.1.0")
    repository_id = await _create_repository(session_factory, repo)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode("utf-8")
        return _chat_response("## [1.1.0]\n### Added\n- second")

    _enable_llm(app)
    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/release-notes",
        json={"from_tag": "v1.0.0", "to_tag": "v1.1.0", "language": "ru"},
    )
    tags = await client.get(f"/api/v1/repositories/{repository_id}/tags")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["changelog"].startswith("## [1.1.0]")
    assert payload["commits"] == 1
    assert payload["cached"] is False
    assert "feat: second" in captured["body"]
    assert tags.status_code == 200
    assert tags.json()["tags"] == ["v1.0.0", "v1.1.0"]


@pytest.mark.asyncio
async def test_release_notes_unknown_tag(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "notag")
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: initial")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    app.state.llm_service = LLMService(app.state.settings)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/release-notes",
        json={"from_tag": "v9.9.9", "to_tag": "HEAD"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tag_not_found:v9.9.9"
