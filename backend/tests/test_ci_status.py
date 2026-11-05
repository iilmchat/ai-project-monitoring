"""CI status aggregation tests (S11-001)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository, RepositoryStatus
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeCI:
    def __init__(self, status: str, conclusion: str | None = None) -> None:
        self._status = status
        self._conclusion = conclusion
        self.configured = True

    async def get_ci_status(self, full_name: str, branch: str) -> dict[str, object]:
        return {
            "provider": "github",
            "status": self._status,
            "conclusion": self._conclusion,
            "url": "https://github.com/acme/app/actions/runs/1",
        }


class FakeGitFlicCI:
    configured = True

    async def get_ci_status(self, full_name: str, branch: str) -> dict[str, object]:
        return {
            "provider": "gitflic",
            "status": "not_supported",
            "conclusion": None,
            "url": None,
        }


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str((tmp_path / "repo").resolve()),
            tracked=True,
            github_full_name="acme/app",
            gitflic_full_name="acme/app",
        )
        session.add(repository)
        await session.flush()
        session.add(
            RepositoryStatus(
                repository_id=repository.id,
                state="current",
                branch="main",
            )
        )
        await session.commit()
        await session.refresh(repository)
        return repository.id


def _install_clients(app: FastAPI, github: FakeCI) -> None:
    app.state.github_client = github
    app.state.gitflic_client = FakeGitFlicCI()


async def test_ci_status_success(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    _install_clients(app, FakeCI("completed", "success"))

    response = await client.get(f"/api/v1/repositories/{repository_id}/ci-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["branch"] == "main"
    assert payload["github"]["conclusion"] == "success"
    assert payload["github"]["url"].endswith("/runs/1")
    assert payload["gitflic"]["status"] == "not_supported"
    assert payload["aggregate"] == "success"


async def test_ci_status_failure(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    _install_clients(app, FakeCI("completed", "failure"))

    response = await client.get(f"/api/v1/repositories/{repository_id}/ci-status")

    assert response.status_code == 200
    assert response.json()["aggregate"] == "failure"


async def test_ci_status_not_configured(
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / "plain").resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        repository_id = repository.id

    response = await client.get(f"/api/v1/repositories/{repository_id}/ci-status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["github"]["status"] == "not_configured"
    assert payload["gitflic"]["status"] == "not_configured"
    assert payload["aggregate"] == "none"


async def test_ci_status_not_found(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/repositories/999999/ci-status")).status_code == 404
