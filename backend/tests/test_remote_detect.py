"""Remote URL auto-detection tests (S60-005)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from app.git.pygit2_backend import detect_remote_names, parse_remote_url
from app.models.entities import Repository
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_parse_remote_url_github_ssh_and_https() -> None:
    expected = {"provider": "github", "full_name": "Acme/Project"}
    assert parse_remote_url("git@github.com:Acme/Project.git") == expected
    assert parse_remote_url("https://github.com/Acme/Project.git") == expected
    assert parse_remote_url("ssh://git@github.com/Acme/Project.git") == expected
    assert parse_remote_url("https://github.com/Acme/Project") == expected


def test_parse_remote_url_gitflic_variants() -> None:
    expected = {"provider": "gitflic", "full_name": "acme/project"}
    assert parse_remote_url("git@gitflic.ru:acme/project.git") == expected
    assert parse_remote_url("ssh://git@gitflic.ru/acme/project.git") == expected
    assert parse_remote_url("https://gitflic.ru/project/acme/project") == expected
    assert parse_remote_url("https://gitflic.ru/project/acme/project.git") == expected


def test_parse_remote_url_rejects_local_paths_and_unknown_hosts() -> None:
    assert parse_remote_url("C:/local/repo") == {
        "provider": "unknown",
        "full_name": None,
    }
    assert parse_remote_url("") == {"provider": "unknown", "full_name": None}
    unknown = parse_remote_url("https://gitlab.com/acme/project.git")
    assert unknown == {"provider": "unknown", "full_name": "acme/project"}


def _add_remote(path: Path, name: str, url: str) -> None:
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", name, url],
        check=True,
        capture_output=True,
    )


def test_detect_remote_names_reads_real_repository(
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    repo = make_repo(tmp_path / "detect")
    _add_remote(repo, "origin", "git@github.com:Acme/Project.git")
    _add_remote(repo, "gitflic", "https://gitflic.ru/project/acme/project.git")

    assert detect_remote_names(repo) == {
        "github": "Acme/Project",
        "gitflic": "acme/project",
    }


def test_detect_remote_names_degrades_for_missing_repository(tmp_path: Path) -> None:
    assert detect_remote_names(tmp_path / "missing") == {
        "github": None,
        "gitflic": None,
    }


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


async def test_repositories_api_detects_remote_names(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    repo = make_repo(tmp_path / "api")
    _add_remote(repo, "origin", "https://github.com/Acme/Api.git")
    _add_remote(repo, "gitflic", "git@gitflic.ru:acme/api.git")
    await _add_repository(session_factory, repo)

    plain = await client.get("/api/v1/repositories")
    assert plain.status_code == 200
    plain_item = plain.json()["items"][0]
    assert plain_item["detected_github_name"] is None
    assert plain_item["detected_gitflic_name"] is None

    detected = await client.get("/api/v1/repositories", params={"detect_remote": "true"})
    assert detected.status_code == 200
    item = detected.json()["items"][0]
    assert item["detected_github_name"] == "Acme/Api"
    assert item["detected_gitflic_name"] == "acme/api"
