"""AI code review tests (S53-002)."""

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


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_enabled": True,
        "llm_base_url": "http://127.0.0.1:1234/v1",
        "llm_model": "test-model",
        "llm_api_key": "",
        "llm_timeout_seconds": 5,
        "llm_max_diff_chars": 10000,
        "llm_allow_remote": False,
        "ai_code_review_max_chars": 40000,
        "ai_code_review_chunk_chars": 5000,
        "ai_code_review_max_chunks": 8,
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


def _seed_repo(repo: Path) -> None:
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")


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
async def test_review_code_chunks_large_diff() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.read().decode("utf-8"))
        return _chat_response(f"review-{len(requests)}")

    service = LLMService(
        _settings(ai_code_review_chunk_chars=100, ai_code_review_max_chunks=10),
        transport=httpx.MockTransport(handler),
    )
    diff = "diff --git a/app.py b/app.py\n" + "".join(
        f"+line-{index}\n" for index in range(80)
    )

    review = await service.review_code(diff)

    assert review is not None
    assert "review-1" in review
    assert "### Часть 2" in review
    assert len(requests) > 1
    assert "Senior Code Reviewer" in requests[0]


@pytest.mark.asyncio
async def test_code_review_api_success_and_cache(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "repo")
    _seed_repo(repo)
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    calls = 0
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        bodies.append(request.read().decode("utf-8"))
        return _chat_response("## Проблемы\n- `app.py:2` — проверьте обработку")

    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    first = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )
    second = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["review"].startswith("## Проблемы")
    assert payload["cached"] is False
    assert payload["files_reviewed"] == 1
    assert payload["truncated"] is False
    assert first.headers["X-AI-Cache"] == "miss"
    assert "+two" in bodies[0]
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.headers["X-AI-Cache"] == "hit"
    assert calls == 1

    (repo / "app.py").write_text("one\nthree\n", encoding="utf-8")
    third = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert third.status_code == 200
    assert third.json()["cached"] is False
    assert calls == 2


@pytest.mark.asyncio
async def test_code_review_api_no_changes(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "clean")
    _seed_repo(repo)
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    app.state.llm_service = LLMService(app.state.settings)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Нет изменений"


@pytest.mark.asyncio
async def test_code_review_api_uses_staged_diff_on_unborn_branch(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "unborn")
    (repo / "app.py").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "-A")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode("utf-8")
        return _chat_response("## OK")

    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 200, response.text
    assert "+staged" in captured["body"]


@pytest.mark.asyncio
async def test_code_review_api_llm_disabled(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "disabled")
    _seed_repo(repo)
    (repo / "app.py").write_text("changed\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    app.state.llm_service = LLMService(
        _settings(llm_enabled=False)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "llm_disabled"


@pytest.mark.asyncio
async def test_code_review_api_llm_unavailable(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "offline")
    _seed_repo(repo)
    (repo / "app.py").write_text("changed\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(app)

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 503
    assert "LLM недоступна" in response.json()["detail"]


@pytest.mark.asyncio
async def test_code_review_api_redacts_secrets(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "secrets")
    _seed_repo(repo)
    secret = "ghp_" + "a" * 40
    (repo / "app.py").write_text(f"TOKEN = '{secret}'\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode("utf-8")
        return _chat_response("## OK")

    _enable_llm(app)
    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 200, response.text
    assert secret not in captured["body"]
    assert "ghp_****" in captured["body"]


@pytest.mark.asyncio
async def test_code_review_api_truncates_and_chunks_large_diff(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "large")
    _seed_repo(repo)
    (repo / "app.py").write_text(
        "".join(f"line-{index}\n" for index in range(200)), encoding="utf-8"
    )
    repository_id = await _create_repository(session_factory, repo)
    _enable_llm(
        app,
        ai_code_review_max_chars=1200,
        ai_code_review_chunk_chars=500,
    )
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _chat_response(f"review-{calls}")

    app.state.llm_service = LLMService(
        app.state.settings, transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/code-review",
        json={"language": "ru"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["truncated"] is True
    assert payload["warnings"] == ["diff_truncated"]
    assert calls > 1
