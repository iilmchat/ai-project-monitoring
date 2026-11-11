"""Smart AI cache by state hash (S43-003)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from app.config import Settings
from app.models.entities import Repository
from app.services.ai_cache import build_cache_key
from app.services.dashboard_advice_service import DashboardAdviceService
from app.services.llm_service import LLMConfig, LLMService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self) -> LLMConfig:
        return LLMConfig(
            enabled=True,
            provider="fake",
            base_url="http://127.0.0.1:1234/v1",
            model="fake-model",
            api_key="",
            timeout=30.0,
            allow_remote=True,
        )

    def allows_remote(self, config: LLMConfig) -> bool:
        return True

    async def generate_dashboard_advice(
        self,
        stats: dict[str, int],
        details: dict[str, object] | None = None,
        *,
        language: str = "ru",
    ) -> str | None:
        self.calls += 1
        return f"advice-{self.calls}"


class FakeDeps:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(summary=SimpleNamespace(outdated=0))


class FakeSecurity:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(ecosystems=[])


def test_cache_key_is_bounded_and_has_no_secrets() -> None:
    key = build_cache_key(
        "feature",
        "scope",
        {"head_sha": "abc", "dirty": 1},
        "model-" + "x" * 300,
        "v1",
    )
    assert key.startswith("feature:scope:")
    assert key.endswith(":v1")
    assert "secret" not in key
    assert len(key) <= 255


@pytest.mark.asyncio
async def test_dashboard_advice_is_reused_until_state_changes(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = DashboardAdviceService(
        session_factory,
        FakeDeps(),  # type: ignore[arg-type]
        FakeSecurity(),  # type: ignore[arg-type]
        llm,  # type: ignore[arg-type]
    )
    stats = {"repositories": 2, "dirty": 1}

    async def fake_context(
        language: str = "ru",
    ) -> tuple[dict[str, int], dict[str, object]]:
        return dict(stats), {"repos_with_ahead": []}

    monkeypatch.setattr(service, "_collect_context", fake_context)

    first = await service.get_advice("ru")
    second = await service.get_advice("ru")

    assert first.cached is False
    assert second.cached is True
    assert second.advice == first.advice
    assert llm.calls == 1

    stats["dirty"] = 2
    third = await service.get_advice("ru")

    assert third.cached is False
    assert third.advice == "advice-2"
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_dashboard_refresh_bypasses_cache(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = DashboardAdviceService(
        session_factory,
        FakeDeps(),  # type: ignore[arg-type]
        FakeSecurity(),  # type: ignore[arg-type]
        llm,  # type: ignore[arg-type]
    )

    async def fake_context(
        language: str = "ru",
    ) -> tuple[dict[str, int], dict[str, object]]:
        return {"repositories": 1}, {}

    monkeypatch.setattr(service, "_collect_context", fake_context)

    first = await service.get_advice("ru", refresh=True)
    second = await service.get_advice("ru", refresh=True)

    assert first.cached is False
    assert second.cached is False
    assert llm.calls == 2


def _settings() -> Settings:
    return Settings(
        llm_enabled=True,
        llm_base_url="http://127.0.0.1:1234/v1",
        llm_model="test-model",
        llm_allow_remote=False,
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


@pytest.mark.asyncio
async def test_commit_message_cache_hits_and_invalidates(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "app.py").write_text("one\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    repository_id = await _create_repository(session_factory, repo)
    (repo / "app.py").write_text("one\ntwo\n", encoding="utf-8")

    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": f"feat: change {calls}"}}]},
        )

    app.state.llm_service = LLMService(
        _settings(),
        transport=httpx.MockTransport(handler),
    )

    first = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )
    second = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert first.status_code == 200, first.text
    assert first.json()["cached"] is False
    assert first.headers["X-AI-Cache"] == "miss"
    assert second.status_code == 200, second.text
    assert second.json()["cached"] is True
    assert second.json()["message"] == first.json()["message"]
    assert second.headers["X-AI-Cache"] == "hit"
    assert calls == 1

    (repo / "app.py").write_text("one\nthree\n", encoding="utf-8")
    third = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/commit-message"
    )

    assert third.status_code == 200, third.text
    assert third.json()["cached"] is False
    assert calls == 2
