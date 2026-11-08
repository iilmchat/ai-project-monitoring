"""Background polling of mirror status (SPEC §3.8.4, S9-007)."""

from __future__ import annotations

import asyncio
from contextlib import suppress

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.entities import Repository
from app.services.mirror_service import MirrorService
from app.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)


class MirrorScheduler:
    """Periodically refresh mirror status for tracked repositories."""

    def __init__(
        self,
        service: MirrorService,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        interval_seconds: float = 300.0,
        notifications: NotificationService | None = None,
    ) -> None:
        self._service = service
        self._session_factory = session_factory
        self._interval = max(interval_seconds, 1.0)
        self._notifications = notifications
        self._last_statuses: dict[int, str] = {}
        self._task: asyncio.Task[None] | None = None

    @property
    def interval_seconds(self) -> float:
        return self._interval

    def set_interval(self, interval_seconds: float) -> None:
        self._interval = max(float(interval_seconds), 1.0)

    def start(self) -> asyncio.Task[None]:
        self._task = asyncio.create_task(self._run(), name="mirror-scheduler")
        return self._task

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("mirror_poll_failed")
            await asyncio.sleep(self._interval)

    async def tick(self) -> int:
        """Refresh all tracked, mirror-expected repositories once."""
        if not self._service.enabled:
            return 0

        async with self._session_factory() as session:
            repositories = (
                await session.scalars(
                    select(Repository).where(
                        Repository.tracked.is_(True),
                        Repository.mirror_expected.is_(True),
                    )
                )
            ).all()

        checked = 0
        for repository in repositories:
            if repository.github_full_name is None and repository.gitflic_full_name is None:
                continue
            try:
                snapshot = await self._service.refresh_mirror_status(repository)
                previous = self._last_statuses.get(repository.id)
                if self._notifications is not None:
                    await asyncio.to_thread(
                        self._notifications.notify_mirror_status,
                        repository.id,
                        repository.path,
                        snapshot.mirror_status,
                        previous,
                    )
                self._last_statuses[repository.id] = snapshot.mirror_status
                checked += 1
            except Exception:
                logger.exception(
                    "mirror_poll_repository_failed",
                    repository_id=repository.id,
                    path=repository.path,
                )
        logger.info("mirror_poll_completed", checked=checked, candidates=len(repositories))
        return checked


__all__ = ["MirrorScheduler"]
