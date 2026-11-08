"""Remote duplicate detection tests (S37-001)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from app.models.entities import Repository
from app.services.identity_service import IdentityService, normalize_remote_url
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_normalize_remote_url_for_https_and_ssh() -> None:
    assert normalize_remote_url("https://github.com/Acme/Project.git") == (
        "github.com/acme/project"
    )
    assert normalize_remote_url("git@github.com:Acme/Project.git") == (
        "github.com/acme/project"
    )
    assert normalize_remote_url("https://gitflic.ru/project/acme/project.git") == (
        "gitflic.ru/project/acme/project"
    )
    assert normalize_remote_url("C:/local/repo") is None


def _add_remote(path: Path, url: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", url],
        check=True,
        capture_output=True,
    )


async def _add_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_identity_service_groups_repositories_by_normalized_remote(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    first = make_repo(tmp_path / "one")
    second = make_repo(tmp_path / "two")
    other = make_repo(tmp_path / "three")
    _add_remote(first, "https://github.com/acme/project.git")
    _add_remote(second, "git@github.com:Acme/Project.git")
    _add_remote(other, "https://github.com/acme/another.git")

    first_id = await _add_repository(session_factory, first)
    second_id = await _add_repository(session_factory, second)
    await _add_repository(session_factory, other)

    groups = await IdentityService(session_factory).find_remote_duplicates()

    assert len(groups) == 1
    assert groups[0].remote_url == "github.com/acme/project"
    assert {item.id for item in groups[0].repositories} == {first_id, second_id}


async def test_duplicates_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    first = make_repo(tmp_path / "api-one")
    second = make_repo(tmp_path / "api-two")
    _add_remote(first, "https://gitflic.ru/project/acme/project.git")
    _add_remote(second, "https://gitflic.ru/project/acme/project.git")
    await _add_repository(session_factory, first)
    await _add_repository(session_factory, second)

    response = await client.get("/api/v1/dashboard/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checked"] == 2
    assert len(payload["groups"]) == 1
    assert payload["groups"][0]["remote_url"] == "gitflic.ru/project/acme/project"
    assert len(payload["groups"][0]["repositories"]) == 2
