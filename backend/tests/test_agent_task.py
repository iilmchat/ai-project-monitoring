"""Agent task generation tests (S38-002)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.models.entities import Repository
from app.schemas.repository import DirtyCountsResponse, RepositoryStatusResponse
from app.services.agent_task_service import AgentTaskService
from app.services.llm_service import LLMConfig
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeLLM:
    enabled = True
    model = "fake-model"

    def __init__(self) -> None:
        self.contexts: list[dict[str, object]] = []

    def remote_allowed(self) -> bool:
        return True

    async def resolve(self) -> LLMConfig:
        return LLMConfig(
            enabled=self.enabled,
            provider="fake",
            base_url="http://127.0.0.1:1234/v1",
            model=self.model,
            api_key="",
            timeout=30.0,
            allow_remote=True,
        )

    def allows_remote(self, config: LLMConfig) -> bool:
        return True

    async def generate_agent_task(
        self,
        context: dict[str, object],
        *,
        language: str = "ru",
    ) -> str | None:
        self.contexts.append(context)
        return f"# Agent task ({language})\n\nFix {context['state']} state."


def _status(repository: Repository, state: str = "dirty") -> RepositoryStatusResponse:
    return RepositoryStatusResponse(
        repository_id=repository.id,
        path=repository.path,
        branch="main",
        head_sha="abc123",
        head_subject="feat: test",
        head_date=datetime.now(UTC),
        upstream="origin/main",
        ahead=0,
        behind=0,
        state=state,
        dirty=DirtyCountsResponse(modified=1, staged=0, untracked=1, conflicted=0),
        detached=False,
        remote_status="ok",
        error=None,
        checked_at=datetime.now(UTC),
    )


def _make_commit(path: Path) -> None:
    (path / "app.py").write_text("print('x')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "-m",
            "feat: initial",
        ],
        check=True,
    )


async def test_agent_task_service_includes_context(
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    repo_path = make_repo(tmp_path / "repo")
    _make_commit(repo_path)
    repository = Repository(id=1, path=str(repo_path), tracked=True)
    llm = FakeLLM()

    task = await AgentTaskService(llm).generate(  # type: ignore[arg-type]
        repository,
        _status(repository),
        language="en",
    )

    assert "Fix dirty state." in task.task
    assert task.model == "fake-model"
    assert llm.contexts[0]["state"] == "dirty"
    assert llm.contexts[0]["commits"] == ["feat: initial"]


async def test_agent_task_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    repo_path = make_repo(tmp_path / "api-repo")
    _make_commit(repo_path)
    async with session_factory() as session:
        repository = Repository(path=str(repo_path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        repository_id = repository.id

    service = AgentTaskService(FakeLLM())  # type: ignore[arg-type]
    app.state.agent_task_service = service

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/agent-task",
        json={"language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task"].startswith("# Agent task")
    assert payload["model"] == "fake-model"
