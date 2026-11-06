"""LLM integration, settings and commit-action tests (S32)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import httpx
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
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _chat_response(message: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": message}}]},
    )


async def test_generate_commit_message_success() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "path": request.url.path,
                "body": request.read().decode("utf-8"),
            }
        )
        return _chat_response("feat: add AI commit generation")

    service = LLMService(
        _settings(llm_api_key="sk-test-key"),
        transport=httpx.MockTransport(handler),
    )

    message = await service.generate_commit_message("diff --git a/x b/x")

    assert message == "feat: add AI commit generation"
    assert requests[0]["path"] == "/v1/chat/completions"
    body = str(requests[0]["body"])
    assert '"model":"test-model"' in body
    assert "Conventional Commits" in body


async def test_generate_commit_message_returns_none_on_connection_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    service = LLMService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    assert await service.generate_commit_message("diff") is None


async def test_generate_commit_message_returns_none_on_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    service = LLMService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    assert await service.generate_commit_message("diff") is None


async def test_disabled_llm_does_not_call_network() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _chat_response("feat: never")

    service = LLMService(
        _settings(llm_enabled=False),
        transport=httpx.MockTransport(handler),
    )

    assert await service.generate_commit_message("diff") is None
    assert called is False


async def test_remote_endpoint_blocked_without_opt_in() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _chat_response("feat: remote")

    service = LLMService(
        _settings(llm_base_url="https://api.example.com/v1"),
        transport=httpx.MockTransport(handler),
    )

    assert service.remote_allowed() is False
    assert await service.generate_commit_message("diff") is None
    assert called is False


async def test_settings_patch_masks_llm_key_and_applies_config(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={
            "llm_enabled": True,
            "llm_base_url": "http://127.0.0.1:11434/v1",
            "llm_model": "qwen-test",
            "llm_api_key": "sk-test-key-1234",
            "llm_timeout_seconds": 20,
            "llm_max_diff_chars": 5000,
            "llm_allow_remote": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["llm_enabled"] is True
    assert payload["llm_model"] == "qwen-test"
    assert payload["llm_timeout_seconds"] == 20
    assert payload["llm_api_key"] == "sk-t****1234"
    assert app.state.settings.llm_enabled is True
    assert app.state.settings.llm_model == "qwen-test"
    assert app.state.settings.llm_base_url == "http://127.0.0.1:11434/v1"


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


async def test_commit_message_api_success(
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
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode("utf-8")
        return _chat_response("feat: add second line")

    app.state.llm_service = LLMService(
        _settings(), transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "feat: add second line"
    assert payload["source"] == "llm"
    assert payload["files_changed"] == 1
    assert payload["truncated"] is False
    assert "+two" in captured["body"]


async def test_commit_message_api_no_changes(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "clean")
    _seed_repo(repo)
    repository_id = await _create_repository(session_factory, repo)
    app.state.llm_service = LLMService(_settings())

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert response.status_code == 400
    assert "Нет изменений" in response.json()["detail"]


async def test_commit_message_api_llm_disabled(
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
    app.state.llm_service = LLMService(_settings(llm_enabled=False))

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "llm_disabled"


async def test_commit_message_api_llm_unavailable(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "unavailable")
    _seed_repo(repo)
    (repo / "app.py").write_text("changed\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    app.state.llm_service = LLMService(
        _settings(), transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert response.status_code == 503
    assert "LLM недоступна" in response.json()["detail"]


async def test_commit_message_api_truncates_large_diff(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "large")
    _seed_repo(repo)
    (repo / "app.py").write_text("x" * 500 + "\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, repo)
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read().decode("utf-8")
        return _chat_response("chore: update generated data")

    app.state.settings.llm_max_diff_chars = 100
    app.state.llm_service = LLMService(
        _settings(), transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["truncated"] is True
    assert payload["warnings"] == ["diff_truncated"]
    assert "[diff truncated]" in captured["body"]


async def test_commit_action_writes_audit_and_commits(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "commit")
    _seed_repo(repo)
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", "-A")
    repository_id = await _create_repository(session_factory, repo)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/commit",
        json={"confirm": True, "message": "feat: commit from dashboard"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "commit"
    assert payload["status"] == "success"
    subject = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    assert subject == "feat: commit from dashboard"


async def test_commit_action_requires_message(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "no-message")
    _seed_repo(repo)
    (repo / "app.py").write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    repository_id = await _create_repository(session_factory, repo)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/commit",
        json={"confirm": True},
    )

    assert response.status_code == 400
    assert "commit message is required" in response.json()["detail"]
