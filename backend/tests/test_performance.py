"""Performance-related tests: fast dirty check (KI-002) and compare cache (KI-003)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from app.git.command_backend import is_repo_dirty_fast
from app.git.pygit2_backend import compare_refs
from app.models.entities import Repository
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

GIT_IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.com")


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *GIT_IDENTITY, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    return path


def _commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-q", "-m", message)
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


def test_fast_dirty_returns_false_for_clean_repo(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "clean")
    _commit(repo, "file.txt", "one\n", "init")

    assert is_repo_dirty_fast(repo) is False


def test_fast_dirty_returns_true_for_modified_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "modified")
    _commit(repo, "file.txt", "one\n", "init")

    (repo / "file.txt").write_text("changed\n", encoding="utf-8")

    assert is_repo_dirty_fast(repo) is True


def test_fast_dirty_returns_true_for_staged_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "staged")
    _commit(repo, "file.txt", "one\n", "init")

    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    _run_git(repo, "add", "new.txt")

    assert is_repo_dirty_fast(repo) is True


def test_fast_dirty_ignores_untracked_only(tmp_path: Path) -> None:
    """``-uno`` intentionally skips untracked files (KI-002 trade-off)."""
    repo = _init_repo(tmp_path / "untracked")
    _commit(repo, "file.txt", "one\n", "init")

    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")

    assert is_repo_dirty_fast(repo) is False


def test_fast_dirty_falls_back_for_invalid_path(tmp_path: Path) -> None:
    assert is_repo_dirty_fast(tmp_path / "missing") is True


def _make_remote_and_clone(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    seed = _init_repo(tmp_path / "seed")
    _commit(seed, "file.txt", "one\n", "init")
    _run_git(seed, "remote", "add", "origin", str(remote))
    _run_git(seed, "push", "-q", "-u", "origin", "main")

    local = tmp_path / "local"
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(local)],
        check=True,
        capture_output=True,
    )
    return local


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()))
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_compare_is_cached(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    local = _make_remote_and_clone(tmp_path)
    repository_id = await _create_repository(session_factory, local)

    with patch(
        "app.api.v1.repositories.compare_refs",
        wraps=compare_refs,
    ) as mocked_compare:
        first = await client.get(f"/api/v1/repositories/{repository_id}/compare")
        second = await client.get(f"/api/v1/repositories/{repository_id}/compare")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "identical"
    assert second.json() == first.json()
    assert mocked_compare.call_count == 1


async def test_refresh_invalidates_compare_cache(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    local = _make_remote_and_clone(tmp_path)
    repository_id = await _create_repository(session_factory, local)

    with patch(
        "app.api.v1.repositories.compare_refs",
        wraps=compare_refs,
    ) as mocked_compare:
        await client.get(f"/api/v1/repositories/{repository_id}/compare")
        assert mocked_compare.call_count == 1

        refreshed = await client.post(
            f"/api/v1/repositories/{repository_id}/refresh",
            json={"fetch": False},
        )
        assert refreshed.status_code == 200

        await client.get(f"/api/v1/repositories/{repository_id}/compare")
        assert mocked_compare.call_count == 2
