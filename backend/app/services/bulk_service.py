"""Bulk repository operations (S13-001)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.git.command_backend import run_git
from app.models.entities import (
    ActionLog,
    Repository,
    RepositoryMirrorStatus,
    RepositoryStatus,
)

logger = structlog.get_logger(__name__)

MIRROR_SYNC_STATUSES = ("behind_gitflic", "missing_on_gitflic")
DEFAULT_CONCURRENCY = 5


class BulkService:
    """Run fetch/push across many repositories with bounded concurrency."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        concurrency: int = DEFAULT_CONCURRENCY,
        fetch_timeout: int = 30,
        action_timeout: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._concurrency = max(concurrency, 1)
        self._fetch_timeout = fetch_timeout
        self._action_timeout = action_timeout

    async def _repositories(self, tracked_only: bool) -> list[Repository]:
        async with self._session_factory() as session:
            statement = select(Repository).order_by(Repository.path)
            if tracked_only:
                statement = statement.where(Repository.tracked.is_(True))
            return list((await session.scalars(statement)).all())

    async def fetch_all(self, tracked_only: bool = True) -> dict[str, Any]:
        repositories = await self._repositories(tracked_only)
        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker(repository: Repository) -> dict[str, Any]:
            async with semaphore:
                result = await asyncio.to_thread(
                    run_git,
                    ["fetch", "--all", "--prune"],
                    cwd=repository.path,
                    timeout=self._fetch_timeout,
                )
                return {
                    "repository_id": repository.id,
                    "path": repository.path,
                    "status": "success" if result.ok else "failed",
                    "error": result.error,
                }

        details = list(await asyncio.gather(*(worker(repo) for repo in repositories)))
        success = sum(1 for item in details if item["status"] == "success")
        summary = {
            "total": len(details),
            "success": success,
            "failed": len(details) - success,
            "details": details,
        }
        logger.info(
            "bulk_fetch_completed",
            total=summary["total"],
            success=summary["success"],
            failed=summary["failed"],
        )
        return summary

    async def sync_mirrors_all(self, tracked_only: bool = True) -> dict[str, Any]:
        async with self._session_factory() as session:
            statement = (
                select(Repository, RepositoryMirrorStatus)
                .join(
                    RepositoryMirrorStatus,
                    RepositoryMirrorStatus.repository_id == Repository.id,
                )
                .where(RepositoryMirrorStatus.mirror_status.in_(MIRROR_SYNC_STATUSES))
                .order_by(Repository.path)
            )
            if tracked_only:
                statement = statement.where(Repository.tracked.is_(True))
            rows = (await session.execute(statement)).all()

        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker(repository: Repository) -> dict[str, Any]:
            async with semaphore:
                branch = await self._branch(repository.id)
                command = f"git push gitflic {branch}"
                started = time.perf_counter()
                result = await asyncio.to_thread(
                    run_git,
                    ["push", "gitflic", branch],
                    cwd=repository.path,
                    timeout=self._action_timeout,
                )
                duration_ms = int((time.perf_counter() - started) * 1000)
                await self._write_action_log(
                    repository.id,
                    command,
                    ok=result.ok,
                    exit_code=result.exit_code,
                    output=result.stdout or result.stderr or None,
                    error=result.error,
                    duration_ms=duration_ms,
                )
                return {
                    "repository_id": repository.id,
                    "path": repository.path,
                    "status": "success" if result.ok else "failed",
                    "command": command,
                    "error": result.error,
                }

        details = list(await asyncio.gather(*(worker(repo) for repo, _ in rows)))
        success = sum(1 for item in details if item["status"] == "success")
        summary = {
            "total": len(details),
            "success": success,
            "failed": len(details) - success,
            "details": details,
        }
        logger.info(
            "bulk_mirror_sync_completed",
            total=summary["total"],
            success=summary["success"],
            failed=summary["failed"],
        )
        return summary

    async def migrate_to_gitflic(self) -> dict[str, Any]:
        async with self._session_factory() as session:
            repositories = (
                await session.scalars(
                    select(Repository).where(Repository.canonical_provider == "github")
                )
            ).all()
            updated = 0
            skipped = 0
            for repository in repositories:
                if not repository.gitflic_full_name:
                    skipped += 1
                    continue
                repository.canonical_provider = "gitflic"
                repository.mirror_policy = "gitflic_to_github"
                mirror_row = await session.scalar(
                    select(RepositoryMirrorStatus).where(
                        RepositoryMirrorStatus.repository_id == repository.id
                    )
                )
                if mirror_row is not None:
                    await session.delete(mirror_row)
                updated += 1
            await session.commit()

        summary = {
            "updated": updated,
            "skipped": skipped,
            "total": len(repositories),
        }
        logger.info(
            "bulk_migration_completed",
            updated=updated,
            skipped=skipped,
            total=len(repositories),
        )
        return summary

    async def _branch(self, repository_id: int) -> str:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RepositoryStatus).where(
                    RepositoryStatus.repository_id == repository_id
                )
            )
        return row.branch if row is not None and row.branch else "main"

    async def _write_action_log(
        self,
        repository_id: int,
        command: str,
        *,
        ok: bool,
        exit_code: int | None,
        output: str | None,
        error: str | None,
        duration_ms: int,
    ) -> None:
        async with self._session_factory() as session:
            session.add(
                ActionLog(
                    repository_id=repository_id,
                    action="push_mirror",
                    command=command,
                    status="success" if ok else "error",
                    exit_code=exit_code,
                    output=(output or "")[:4000] or None,
                    error=error,
                    duration_ms=duration_ms,
                    actor="bulk",
                    created_at=utcnow(),
                )
            )
            await session.commit()


__all__ = ["MIRROR_SYNC_STATUSES", "BulkService"]
