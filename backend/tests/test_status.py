"""Status service and API tests on real repositories (S2-001..S2-005).

All 8 canonical states from SPEC §3.4 are covered:
current, dirty, ahead, behind, diverged, no_upstream, detached, error.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from app.git.pygit2_backend import DirtyCounts, GitStatusError, read_local_status
from app.models.entities import Repository
from app.services.status_service import (
    StatusCache,
    StatusService,
    StatusSnapshot,
    classify_state,
)
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


def _init_work_repo(path: Path) -> Path:
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        check=True,
        capture_output=True,
    )
    return path


def _commit(repo: Path, filename: str, content: str, message: str) -> None:
    (repo / filename).write_text(content, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-q", "-m", message)


def _make_repo_with_upstream(tmp_path: Path) -> tuple[Path, Path]:
    """Create a work repository pushed to a local bare remote."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-q", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )
    work = _init_work_repo(tmp_path / "work")
    _commit(work, "file.txt", "one\n", "init")
    _run_git(work, "remote", "add", "origin", str(remote))
    _run_git(work, "push", "-q", "-u", "origin", "main")
    return remote, work


def _push_remote_commit(remote: Path, clone: Path, message: str) -> None:
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    _commit(clone, f"{clone.name}.txt", f"{message}\n", message)
    _run_git(clone, "push", "-q", "origin", "main")


@pytest.fixture
def service() -> StatusService:
    return StatusService(StatusCache(ttl_seconds=60), ttl_seconds=60)


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()))
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def _refresh(
    service: StatusService,
    session_factory: async_sessionmaker[AsyncSession],
    repository_id: int,
) -> StatusSnapshot:
    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        return await service.refresh(session, repository)


async def test_current(service, session_factory, tmp_path: Path) -> None:
    _, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "current"
    assert snapshot.branch == "main"
    assert snapshot.upstream == "origin/main"
    assert snapshot.ahead == 0
    assert snapshot.behind == 0
    assert snapshot.dirty == DirtyCounts()
    assert snapshot.detached is False
    assert snapshot.head_sha is not None
    assert snapshot.head_subject == "init"
    assert snapshot.head_date is not None
    assert snapshot.error is None


async def test_dirty(service, session_factory, tmp_path: Path) -> None:
    _, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    (work / "file.txt").write_text("modified\n", encoding="utf-8")
    (work / "staged.txt").write_text("staged\n", encoding="utf-8")
    _run_git(work, "add", "staged.txt")
    (work / "untracked.txt").write_text("untracked\n", encoding="utf-8")

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "dirty"
    assert snapshot.dirty.modified == 1
    assert snapshot.dirty.staged == 1
    assert snapshot.dirty.untracked == 1
    assert snapshot.dirty.conflicted == 0


async def test_ahead(service, session_factory, tmp_path: Path) -> None:
    _, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    _commit(work, "local.txt", "local\n", "local only")

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "ahead"
    assert snapshot.ahead == 1
    assert snapshot.behind == 0
    assert snapshot.dirty.total == 0


async def test_behind(service, session_factory, tmp_path: Path) -> None:
    remote, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    _push_remote_commit(remote, tmp_path / "clone", "remote commit")
    _run_git(work, "fetch", "-q", "origin")

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "behind"
    assert snapshot.ahead == 0
    assert snapshot.behind == 1


async def test_diverged(service, session_factory, tmp_path: Path) -> None:
    remote, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    _commit(work, "local.txt", "local\n", "local commit")
    _push_remote_commit(remote, tmp_path / "clone", "remote commit")
    _run_git(work, "fetch", "-q", "origin")

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "diverged"
    assert snapshot.ahead == 1
    assert snapshot.behind == 1


async def test_no_upstream(service, session_factory, tmp_path: Path) -> None:
    solo = _init_work_repo(tmp_path / "solo")
    _commit(solo, "file.txt", "one\n", "init")
    repository_id = await _create_repository(session_factory, solo)

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "no_upstream"
    assert snapshot.upstream is None
    assert snapshot.ahead == 0
    assert snapshot.behind == 0


async def test_detached(service, session_factory, tmp_path: Path) -> None:
    _, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)
    head_sha = _run_git(work, "rev-parse", "HEAD").stdout.strip()

    _run_git(work, "checkout", "-q", head_sha)

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "detached"
    assert snapshot.detached is True
    assert snapshot.branch is None


async def test_error(service, session_factory, tmp_path: Path) -> None:
    repository_id = await _create_repository(session_factory, tmp_path / "missing-repo")

    snapshot = await _refresh(service, session_factory, repository_id)

    assert snapshot.state == "error"
    assert snapshot.error is not None
    assert snapshot.remote_status == "unavailable"


def test_read_local_status_error(tmp_path: Path) -> None:
    with pytest.raises(GitStatusError):
        read_local_status(tmp_path / "does-not-exist")


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {"detached": True, "has_upstream": True, "ahead": 2, "behind": 1, "dirty_total": 3},
            "detached",
        ),
        (
            {"detached": False, "has_upstream": False, "ahead": 1, "behind": 1, "dirty_total": 2},
            "no_upstream",
        ),
        (
            {"detached": False, "has_upstream": True, "ahead": 1, "behind": 1, "dirty_total": 1},
            "dirty",
        ),
        (
            {"detached": False, "has_upstream": True, "ahead": 1, "behind": 1, "dirty_total": 0},
            "diverged",
        ),
        (
            {"detached": False, "has_upstream": True, "ahead": 1, "behind": 0, "dirty_total": 0},
            "ahead",
        ),
        (
            {"detached": False, "has_upstream": True, "ahead": 0, "behind": 1, "dirty_total": 0},
            "behind",
        ),
        (
            {"detached": False, "has_upstream": True, "ahead": 0, "behind": 0, "dirty_total": 0},
            "current",
        ),
    ],
)
def test_classify_state(kwargs: dict[str, bool | int], expected: str) -> None:
    assert classify_state(**kwargs) == expected  # type: ignore[arg-type]


async def test_status_api_caches_until_refresh(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    _, work = _make_repo_with_upstream(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    first = await client.get(f"/api/v1/repositories/{repository_id}/status")
    assert first.status_code == 200
    payload = first.json()
    assert payload["state"] == "current"
    assert payload["dirty"] == {
        "modified": 0,
        "staged": 0,
        "untracked": 0,
        "conflicted": 0,
    }
    assert payload["upstream"] == "origin/main"

    (work / "file.txt").write_text("changed\n", encoding="utf-8")

    cached = await client.get(f"/api/v1/repositories/{repository_id}/status")
    assert cached.status_code == 200
    assert cached.json()["state"] == "current"

    refreshed = await client.post(f"/api/v1/repositories/{repository_id}/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["state"] == "dirty"
    assert refreshed.json()["dirty"]["modified"] == 1


async def test_status_api_error_state(client: AsyncClient, session_factory, tmp_path: Path) -> None:
    repository_id = await _create_repository(session_factory, tmp_path / "gone")

    response = await client.get(f"/api/v1/repositories/{repository_id}/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "error"
    assert payload["error"]


async def test_status_api_not_found(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/repositories/999999/status")).status_code == 404
    assert (await client.post("/api/v1/repositories/999999/refresh")).status_code == 404
