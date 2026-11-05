"""Confirmed mutation actions and audit tests (S10-001..S10-006)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from app.models.entities import ActionLog, Repository, RepositoryStatus
from httpx import AsyncClient
from sqlalchemy import select
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


def _make_remote_and_work(tmp_path: Path) -> tuple[Path, Path]:
    remote = _init_repo(tmp_path / "remote.git", bare=True)
    work = _init_repo(tmp_path / "work")
    _commit(work, "file.txt", "one\n", "init")
    _run_git(work, "remote", "add", "origin", str(remote))
    _run_git(work, "push", "-q", "-u", "origin", "main")
    return remote, work


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
    *,
    gitflic_full_name: str | None = None,
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str(path.resolve()),
            tracked=True,
            gitflic_full_name=gitflic_full_name,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_action_requires_confirm(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/push",
        json={"confirm": False},
    )

    assert response.status_code == 400
    assert "confirm" in response.json()["detail"].lower()
    async with session_factory() as session:
        assert await session.scalar(select(ActionLog)) is None


async def test_push_action_and_audit(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    remote, work = _make_remote_and_work(tmp_path)
    _commit(work, "local.txt", "local\n", "local commit")
    repository_id = await _create_repository(session_factory, work)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/push",
        json={"confirm": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["action"] == "push"
    assert payload["command"].startswith("git push")

    remote_head = _run_git(remote, "rev-parse", "main").stdout.strip()
    local_head = _run_git(work, "rev-parse", "HEAD").stdout.strip()
    assert remote_head == local_head

    audit = await client.get(f"/api/v1/admin/actions?repository_id={repository_id}")
    assert audit.status_code == 200
    assert len(audit.json()) == 1
    assert audit.json()[0]["status"] == "success"


async def test_stash_action(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    _, work = _make_remote_and_work(tmp_path)
    (work / "file.txt").write_text("dirty\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, work)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/stash",
        json={"confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    status = _run_git(work, "status", "--porcelain").stdout
    assert status == ""


async def test_pull_action(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
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
    _commit(seed, "remote.txt", "remote\n", "remote update")
    _run_git(seed, "push", "-q", "origin", "main")
    repository_id = await _create_repository(session_factory, local)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/pull",
        json={"confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    remote_head = _run_git(remote, "rev-parse", "main").stdout.strip()
    local_head = _run_git(local, "rev-parse", "HEAD").stdout.strip()
    assert local_head == remote_head


async def test_fetch_action(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    _, work = _make_remote_and_work(tmp_path)
    repository_id = await _create_repository(session_factory, work)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/fetch",
        json={"confirm": True},
    )

    assert response.status_code == 200
    assert response.json()["action"] == "fetch"
    assert response.json()["status"] == "success"


async def test_unknown_action(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/reset",
        json={"confirm": True},
    )

    assert response.status_code == 400
    assert "allowed" in response.json()["detail"]


async def test_audit_endpoint_filters(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    first = await _create_repository(session_factory, tmp_path / "one")
    second = await _create_repository(session_factory, tmp_path / "two")

    for repository_id, action in ((first, "stash"), (second, "push")):
        await client.post(
            f"/api/v1/repositories/{repository_id}/actions/{action}",
            json={"confirm": True},
        )

    filtered = await client.get(f"/api/v1/admin/actions?repository_id={first}")
    assert filtered.status_code == 200
    entries = filtered.json()
    assert len(entries) == 1
    assert entries[0]["repository_id"] == first


async def test_mirror_push_action(
    session_factory, client: AsyncClient, tmp_path: Path
) -> None:
    remote = _init_repo(tmp_path / "gitflic.git", bare=True)
    work = _init_repo(tmp_path / "work")
    _commit(work, "file.txt", "one\n", "init")
    _run_git(work, "remote", "add", "gitflic", str(remote))
    repository_id = await _create_repository(
        session_factory, work, gitflic_full_name="acme/app"
    )
    async with session_factory() as session:
        session.add(RepositoryStatus(repository_id=repository_id, state="current", branch="main"))
        await session.commit()

    denied = await client.post(
        "/api/v1/mirror/actions/push-mirror",
        json={"confirm": False, "repository_id": repository_id},
    )
    assert denied.status_code == 400

    response = await client.post(
        "/api/v1/mirror/actions/push-mirror",
        json={"confirm": True, "repository_id": repository_id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["action"] == "push_mirror"
    remote_head = _run_git(remote, "rev-parse", "main").stdout.strip()
    local_head = _run_git(work, "rev-parse", "HEAD").stdout.strip()
    assert remote_head == local_head
