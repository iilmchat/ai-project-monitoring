"""Dependency update preflight, commands and API tests (S34-001)."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from app.models.entities import ActionLog, Repository
from app.services.dependency_update_service import (
    CommandResult,
    DependencyUpdateError,
    DependencyUpdateService,
    run_command,
)
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class HybridRunner:
    """Real ``git`` for preflight, fake package-manager commands."""

    def __init__(self, result: CommandResult) -> None:
        self.result = result
        self.calls: list[list[str]] = []

    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> CommandResult:
        if args and args[0] == "git":
            return await run_command(args, cwd, timeout)
        self.calls.append(list(args))
        return self.result


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


def _clean_repo(
    make_repo: Callable[[Path], Path],
    root: Path,
    files: dict[str, str],
) -> Path:
    repo = make_repo(root)
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    return repo


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


async def test_python_update_runs_after_clean_preflight(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(
        make_repo,
        tmp_path / "clean",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    repository_id = await _create_repository(session_factory, repo)
    runner = HybridRunner(
        CommandResult(ok=True, exit_code=0, stdout="Successfully installed")
    )
    service = DependencyUpdateService(session_factory, runner=runner)

    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        entry = await service.update(
            session, repository, "python", confirm=True
        )

    assert entry.status == "success"
    assert entry.action == "update-dependencies"
    assert entry.command == "pip install -r requirements.txt --upgrade"
    assert entry.actor == "local"
    assert runner.calls == [
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
            "--upgrade",
        ]
    ]
    assert entry.output == "Successfully installed"


async def test_dirty_worktree_blocks_update_and_logs_error(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(
        make_repo,
        tmp_path / "dirty",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    (repo / "requirements.txt").write_text(
        "fastapi==0.115.0\n", encoding="utf-8"
    )
    repository_id = await _create_repository(session_factory, repo)
    runner = HybridRunner(
        CommandResult(ok=True, exit_code=0, stdout="should-not-run")
    )
    service = DependencyUpdateService(session_factory, runner=runner)

    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        try:
            await service.update(session, repository, "python", confirm=True)
        except DependencyUpdateError as exc:
            assert exc.status_code == 409
            assert exc.message == "Worktree must be clean"
        else:  # pragma: no cover - safety net
            raise AssertionError("dirty worktree must be rejected")

    assert runner.calls == []
    async with session_factory() as session:
        logs = (
            await session.scalars(
                select(ActionLog).where(
                    ActionLog.repository_id == repository_id
                )
            )
        ).all()
    assert any(
        item.action == "update-dependencies"
        and item.status == "error"
        and item.error == "dirty_worktree"
        for item in logs
    )


async def test_missing_manifest_is_logged_and_rejected(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(make_repo, tmp_path / "empty", {"README.md": "x\n"})
    repository_id = await _create_repository(session_factory, repo)
    service = DependencyUpdateService(session_factory, runner=HybridRunner(CommandResult(True, 0)))

    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        try:
            await service.update(session, repository, "python", confirm=True)
        except DependencyUpdateError as exc:
            assert exc.message == "no_manifest"
        else:  # pragma: no cover
            raise AssertionError("missing manifest must be rejected")


async def test_node_uses_pnpm_when_lockfile_exists(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(
        make_repo,
        tmp_path / "node",
        {
            "package.json": '{"dependencies": {"react": "^19.0.0"}}',
            "pnpm-lock.yaml": "lockfileVersion: 9\n",
        },
    )
    repository_id = await _create_repository(session_factory, repo)
    runner = HybridRunner(CommandResult(True, 0, stdout="updated"))
    service = DependencyUpdateService(session_factory, runner=runner)

    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        entry = await service.update(session, repository, "node", confirm=True)

    assert entry.command == "pnpm update"
    assert runner.calls == [["pnpm", "update"]]


async def test_output_is_capped_and_credentials_redacted(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(
        make_repo,
        tmp_path / "redact",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    repository_id = await _create_repository(session_factory, repo)
    runner = HybridRunner(
        CommandResult(
            True,
            0,
            stdout=(
                "fetch https://user:secret@example.com/simple\n"
                + "x" * 20000
            ),
        )
    )
    service = DependencyUpdateService(
        session_factory,
        max_output_chars=1000,
        runner=runner,
    )

    async with session_factory() as session:
        repository = await session.get(Repository, repository_id)
        assert repository is not None
        entry = await service.update(session, repository, "python", confirm=True)

    assert entry.output is not None
    assert "user:secret" not in entry.output
    assert "https://****@example.com" in entry.output
    assert len(entry.output) <= 1000 + len("\n… (truncated)")


async def test_update_api_and_dirty_conflict(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    clean = _clean_repo(
        make_repo,
        tmp_path / "api-clean",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    clean_id = await _create_repository(session_factory, clean)
    runner = HybridRunner(CommandResult(True, 0, stdout="ok"))
    app.state.dependency_update_service = DependencyUpdateService(
        session_factory, runner=runner
    )

    response = await client.post(
        f"/api/v1/repositories/{clean_id}/actions/update-dependencies",
        json={"confirm": True, "ecosystem": "python"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["action"] == "update-dependencies"

    dirty = _clean_repo(
        make_repo,
        tmp_path / "api-dirty",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    (dirty / "requirements.txt").write_text("fastapi==0.115.0\n", encoding="utf-8")
    dirty_id = await _create_repository(session_factory, dirty)

    response = await client.post(
        f"/api/v1/repositories/{dirty_id}/actions/update-dependencies",
        json={"confirm": True, "ecosystem": "python"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Worktree must be clean"


async def test_update_api_requires_confirmation(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    make_repo: Callable[[Path], Path],
    tmp_path: Path,
) -> None:
    repo = _clean_repo(
        make_repo,
        tmp_path / "confirm",
        {"requirements.txt": "fastapi==0.110.0\n"},
    )
    repository_id = await _create_repository(session_factory, repo)
    app.state.dependency_update_service = DependencyUpdateService(
        session_factory, runner=HybridRunner(CommandResult(True, 0))
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/actions/update-dependencies",
        json={"confirm": False, "ecosystem": "python"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "confirmation_required"


async def test_bulk_update_returns_accepted(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/repositories/actions/update_dependencies_all",
        json={"confirm": True, "ecosystem": "node"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
