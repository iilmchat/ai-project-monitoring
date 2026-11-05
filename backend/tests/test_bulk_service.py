"""Bulk operation tests (S13-001)."""

from __future__ import annotations

from pathlib import Path

from app.git.command_backend import CommandResult
from app.models.entities import ActionLog, Repository, RepositoryMirrorStatus
from app.services.bulk_service import BulkService
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _ok() -> CommandResult:
    return CommandResult(ok=True, exit_code=0, stdout="ok", stderr="")


def _fail() -> CommandResult:
    return CommandResult(
        ok=False,
        exit_code=1,
        stdout="",
        stderr="boom",
        error="boom",
    )


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    name: str,
    *,
    tracked: bool = True,
    mirror_status: str | None = None,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str((tmp_path / name).resolve()), tracked=tracked)
        session.add(repository)
        await session.flush()
        if mirror_status is not None:
            session.add(
                RepositoryMirrorStatus(
                    repository_id=repository.id,
                    mirror_status=mirror_status,
                    details={},
                )
            )
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_fetch_all_handles_success_and_failure(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    await _create_repository(session_factory, tmp_path, "ok")
    await _create_repository(session_factory, tmp_path, "bad")
    await _create_repository(session_factory, tmp_path, "untracked", tracked=False)

    def fake_run_git(args, *, cwd, timeout):
        return _ok() if "ok" in str(cwd) else _fail()

    monkeypatch.setattr("app.services.bulk_service.run_git", fake_run_git)
    service = BulkService(session_factory)

    result = await service.fetch_all(tracked_only=True)

    assert result["total"] == 2
    assert result["success"] == 1
    assert result["failed"] == 1
    assert {item["status"] for item in result["details"]} == {"success", "failed"}


async def test_fetch_all_includes_untracked_when_disabled(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    await _create_repository(session_factory, tmp_path, "tracked")
    await _create_repository(session_factory, tmp_path, "untracked", tracked=False)
    monkeypatch.setattr(
        "app.services.bulk_service.run_git",
        lambda args, *, cwd, timeout: _ok(),
    )

    result = await BulkService(session_factory).fetch_all(tracked_only=False)

    assert result["total"] == 2
    assert result["success"] == 2


async def test_sync_mirrors_logs_actions(
    session_factory, tmp_path: Path, monkeypatch
) -> None:
    behind_id = await _create_repository(
        session_factory, tmp_path, "behind", mirror_status="behind_gitflic"
    )
    await _create_repository(
        session_factory, tmp_path, "clean", mirror_status="in_sync"
    )
    await _create_repository(
        session_factory,
        tmp_path,
        "missing",
        tracked=False,
        mirror_status="missing_on_gitflic",
    )

    monkeypatch.setattr(
        "app.services.bulk_service.run_git",
        lambda args, *, cwd, timeout: _ok(),
    )

    result = await BulkService(session_factory).sync_mirrors_all(tracked_only=True)

    assert result["total"] == 1
    assert result["success"] == 1
    async with session_factory() as session:
        logs = (await session.scalars(select(ActionLog))).all()
    assert len(logs) == 1
    assert logs[0].repository_id == behind_id
    assert logs[0].action == "push_mirror"
    assert logs[0].actor == "bulk"
    assert logs[0].status == "success"


async def test_bulk_api_returns_202(app, client: AsyncClient) -> None:
    calls: list[bool] = []

    class FakeBulk:
        async def fetch_all(self, tracked_only: bool = True) -> dict[str, object]:
            calls.append(tracked_only)
            return {"total": 0, "success": 0, "failed": 0, "details": []}

    app.state.bulk_service = FakeBulk()

    response = await client.post("/api/v1/repositories/actions/fetch_all")

    assert response.status_code == 202
    assert response.json()["action"] == "fetch_all"
    assert calls == [True]
