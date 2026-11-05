"""Mirror API tests (S9-005, S9-006)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.models.entities import Repository
from app.providers.base import BranchResult
from app.services.mirror_service import MirrorService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeClient:
    def __init__(self, sha: str = "abc123") -> None:
        self._sha = sha
        self.configured = True

    async def get_branch(self, full_name: str, branch: str) -> BranchResult:
        return BranchResult(sha=self._sha, date=datetime(2026, 1, 1, tzinfo=UTC))

    async def list_repos(self) -> list[dict[str, object]]:
        return [
            {"provider": "github", "full_name": "acme/app", "private": True},
            {"provider": "github", "full_name": "acme/github-only", "private": True},
        ]


class FakeGitFlicClient(FakeClient):
    async def list_repos(self) -> list[dict[str, object]]:
        return [
            {"provider": "gitflic", "full_name": "acme/app", "private": True},
            {"provider": "gitflic", "full_name": "acme/gitflic-only", "private": True},
        ]


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
        await session.commit()
        await session.refresh(repository)
        return repository.id


def _install_service(app: FastAPI, session_factory: async_sessionmaker[AsyncSession]) -> None:
    app.state.mirror_service = MirrorService(
        session_factory,
        FakeClient(),  # type: ignore[arg-type]
        FakeGitFlicClient(),  # type: ignore[arg-type]
    )


async def test_mirror_endpoints(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    _install_service(app, session_factory)

    first = await client.get(f"/api/v1/repositories/{repository_id}/mirror")
    assert first.status_code == 200
    payload = first.json()
    assert payload["mirror_status"] == "in_sync"
    assert payload["github"]["head_sha"] == "abc123"
    assert payload["gitflic"]["head_sha"] == "abc123"
    assert payload["canonical_provider"] == "github"
    assert payload["mirror_expected"] is True

    refreshed = await client.post(
        f"/api/v1/repositories/{repository_id}/mirror/refresh"
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["mirror_status"] == "in_sync"

    patched = await client.patch(
        f"/api/v1/repositories/{repository_id}/mirror-policy",
        json={"canonical_provider": "gitflic", "mirror_expected": False},
    )
    assert patched.status_code == 200
    assert patched.json()["canonical_provider"] == "gitflic"
    assert patched.json()["mirror_expected"] is False

    after_policy = await client.get(f"/api/v1/repositories/{repository_id}/mirror")
    assert after_policy.status_code == 200
    assert after_policy.json()["mirror_status"] == "not_applicable"


async def test_mirror_candidates(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
) -> None:
    _install_service(app, session_factory)

    response = await client.get("/api/v1/mirror/candidates")
    assert response.status_code == 200
    payload = response.json()
    assert [item["full_name"] for item in payload["github_only"]] == ["acme/github-only"]
    assert [item["full_name"] for item in payload["gitflic_only"]] == ["acme/gitflic-only"]
    assert len(payload["both"]) == 1
    assert payload["unknown"] == []


async def test_mirror_not_found(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/repositories/999999/mirror")).status_code == 404
    assert (
        await client.patch(
            "/api/v1/repositories/999999/mirror-policy",
            json={"mirror_expected": False},
        )
    ).status_code == 404


async def test_mirror_policy_validation(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    _install_service(app, session_factory)

    response = await client.patch(
        f"/api/v1/repositories/{repository_id}/mirror-policy",
        json={"canonical_provider": "bitbucket"},
    )
    assert response.status_code == 422
