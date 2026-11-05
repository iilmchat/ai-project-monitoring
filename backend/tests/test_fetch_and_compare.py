"""Fetch, remote status, compare and log tests (S3-001..S3-005)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.models.entities import Repository
from app.services.remote_service import RemoteService
from app.services.status_service import StatusCache, StatusService, StatusSnapshot
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


def _init_repo(path: Path, *, bare: bool = False) -> Path:
    args = ["git", "init", "-q", "-b", "main"]
    if bare:
        args.append("--bare")
    args.append(str(path))
    subprocess.run(args, check=True, capture_output=True)
    return path


def _commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content, encoding="utf-8")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-q", "-m", message)
    return _run_git(repo, "rev-parse", "HEAD").stdout.strip()


def _make_remote_and_clone(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create a bare remote, a seed clone and a local clone."""
    remote = _init_repo(tmp_path / "remote.git", bare=True)
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
    return remote, seed, local


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession], path: Path
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()))
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


def _remote_service() -> RemoteService:
    return RemoteService(timeout_seconds=10)


def _status_service() -> StatusService:
    return StatusService(
        StatusCache(ttl_seconds=60),
        ttl_seconds=60,
        remote_service=_remote_service(),
    )


async def _refresh(
    service: StatusService,
    session_factory: async_sessionmaker[AsyncSession],
    repository_id: int,
    *,
    fetch: bool = True,
) -> StatusSnapshot:
    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        return await service.refresh(session, repository, fetch=fetch)


async def test_fetch_success_updates_ahead_behind(
    session_factory, tmp_path: Path
) -> None:
    remote, seed, local = _make_remote_and_clone(tmp_path)
    repository_id = await _create_repository(session_factory, local)

    _commit(seed, "remote.txt", "remote\n", "remote update")
    _run_git(seed, "push", "-q", "origin", "main")

    snapshot = await _refresh(_status_service(), session_factory, repository_id, fetch=True)

    assert snapshot.remote_status == "ok"
    assert snapshot.state == "behind"
    assert snapshot.behind == 1
    assert snapshot.ahead == 0
    assert snapshot.error is None


async def test_refresh_without_fetch_keeps_stale(
    session_factory, tmp_path: Path
) -> None:
    remote, seed, local = _make_remote_and_clone(tmp_path)
    repository_id = await _create_repository(session_factory, local)

    _commit(seed, "remote.txt", "remote\n", "remote update")
    _run_git(seed, "push", "-q", "origin", "main")

    snapshot = await _refresh(_status_service(), session_factory, repository_id, fetch=False)

    assert snapshot.remote_status == "stale"
    assert snapshot.behind == 0


async def test_fetch_failure_marks_unavailable(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    broken = _init_repo(tmp_path / "offline")
    _commit(broken, "file.txt", "one\n", "init")
    _run_git(broken, "remote", "add", "origin", str(tmp_path / "missing.git"))
    _run_git(broken, "config", "branch.main.remote", "origin")
    _run_git(broken, "config", "branch.main.merge", "refs/heads/main")
    repository_id = await _create_repository(session_factory, broken)

    snapshot = await _refresh(_status_service(), session_factory, repository_id, fetch=True)

    assert snapshot.remote_status == "unavailable"
    assert snapshot.state == "current"
    assert snapshot.error is None

    response = await client.post(f"/api/v1/repositories/{repository_id}/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["remote_status"] == "unavailable"
    assert payload["state"] == "current"


async def test_compare_api(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    _, _, local = _make_remote_and_clone(tmp_path)
    repository_id = await _create_repository(session_factory, local)

    identical = await client.get(f"/api/v1/repositories/{repository_id}/compare")
    assert identical.status_code == 200
    body = identical.json()
    assert body["status"] == "identical"
    assert body["ahead"] == 0
    assert body["behind"] == 0
    assert body["commits"] == []

    base_sha = _run_git(local, "rev-parse", "HEAD").stdout.strip()
    new_sha = _commit(local, "local.txt", "local\n", "local commit")

    # The compare cache (KI-003) is invalidated by an explicit refresh.
    await client.post(
        f"/api/v1/repositories/{repository_id}/refresh",
        json={"fetch": False},
    )

    ahead = await client.get(f"/api/v1/repositories/{repository_id}/compare")
    assert ahead.status_code == 200
    body = ahead.json()
    assert body["status"] == "ahead"
    assert body["ahead"] == 1
    assert body["behind"] == 0
    assert len(body["commits"]) == 1
    assert body["commits"][0]["sha"] == new_sha
    assert body["commits"][0]["subject"] == "local commit"
    assert body["commits"][0]["author"] == "Test"
    assert body["commits"][0]["date"]

    explicit = await client.get(
        f"/api/v1/repositories/{repository_id}/compare",
        params={"base": base_sha, "head": "HEAD"},
    )
    assert explicit.status_code == 200
    assert explicit.json()["ahead"] == 1

    unknown_ref = await client.get(
        f"/api/v1/repositories/{repository_id}/compare",
        params={"base": "origin/does-not-exist"},
    )
    assert unknown_ref.status_code == 200
    assert unknown_ref.json()["status"] == "unavailable"


async def test_compare_without_upstream_is_unavailable(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    solo = _init_repo(tmp_path / "solo")
    _commit(solo, "file.txt", "one\n", "init")
    repository_id = await _create_repository(session_factory, solo)

    response = await client.get(f"/api/v1/repositories/{repository_id}/compare")
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"


async def test_log_api(session_factory, client: AsyncClient, tmp_path: Path) -> None:
    solo = _init_repo(tmp_path / "solo")
    first = _commit(solo, "file.txt", "one\n", "first commit")
    second = _commit(solo, "two.txt", "two\n", "second commit")
    third = _commit(solo, "three.txt", "three\n", "third commit")
    repository_id = await _create_repository(session_factory, solo)

    response = await client.get(f"/api/v1/repositories/{repository_id}/log", params={"limit": 5})
    assert response.status_code == 200
    commits = response.json()
    assert len(commits) == 3
    assert commits[0]["sha"] == third
    assert commits[0]["subject"] == "third commit"
    assert commits[0]["author"] == "Test"
    assert "date" in commits[0]
    assert {commit["sha"] for commit in commits} == {first, second, third}

    limited = await client.get(f"/api/v1/repositories/{repository_id}/log", params={"limit": 2})
    assert limited.status_code == 200
    assert len(limited.json()) == 2


async def test_log_api_broken_repository(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path / "missing")
    response = await client.get(f"/api/v1/repositories/{repository_id}/log")
    assert response.status_code == 200
    assert response.json() == []
