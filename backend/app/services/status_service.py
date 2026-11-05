"""Local status service and canonical state classification (SPEC §3.4)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import observe_status_duration
from app.db.base import utcnow
from app.git.command_backend import rev_list_counts
from app.git.pygit2_backend import DirtyCounts, GitStatusError, LocalStatus, read_local_status
from app.models.entities import Repository, RepositoryStatus
from app.services.notification_service import NotificationService
from app.services.remote_service import RemoteService

logger = structlog.get_logger(__name__)

CANONICAL_STATES: frozenset[str] = frozenset(
    {
        "current",
        "behind",
        "ahead",
        "diverged",
        "dirty",
        "no_upstream",
        "detached",
        "error",
    }
)

REMOTE_STATUS_STALE = "stale"
REMOTE_STATUS_UNAVAILABLE = "unavailable"
REMOTE_STATUS_OK = "ok"


def classify_state(
    *,
    detached: bool,
    has_upstream: bool,
    ahead: int,
    behind: int,
    dirty_total: int,
) -> str:
    """Return the canonical state for a local repository snapshot.

    Priority follows ARCHITECTURE §4: ``detached`` and ``no_upstream`` are
    structural states, then ``dirty`` > ``diverged`` > ``ahead`` > ``behind`` >
    ``current``. ``dirty`` and ``ahead/behind`` stay orthogonal in the data
    model: only the single ``state`` field collapses them.
    """
    if detached:
        return "detached"
    if not has_upstream:
        return "no_upstream"
    if dirty_total > 0:
        return "dirty"
    if ahead > 0 and behind > 0:
        return "diverged"
    if ahead > 0:
        return "ahead"
    if behind > 0:
        return "behind"
    return "current"


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Canonical status of a repository, ready for API serialization."""

    repository_id: int
    path: str
    state: str
    branch: str | None = None
    head_sha: str | None = None
    head_subject: str | None = None
    head_date: datetime | None = None
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    dirty: DirtyCounts = field(default_factory=DirtyCounts)
    detached: bool = False
    remote_status: str = REMOTE_STATUS_STALE
    error: str | None = None
    checked_at: datetime = field(default_factory=utcnow)


class StatusCache:
    """In-memory TTL cache for status snapshots."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = max(ttl_seconds, 0)
        self._items: dict[int, tuple[float, StatusSnapshot]] = {}

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def get(self, repository_id: int) -> StatusSnapshot | None:
        entry = self._items.get(repository_id)
        if entry is None:
            return None
        stored_at, snapshot = entry
        if self._ttl <= 0 or (time.monotonic() - stored_at) >= self._ttl:
            self._items.pop(repository_id, None)
            return None
        return snapshot

    def set(self, snapshot: StatusSnapshot) -> None:
        self._items[snapshot.repository_id] = (time.monotonic(), snapshot)

    def invalidate(self, repository_id: int | None = None) -> None:
        if repository_id is None:
            self._items.clear()
        else:
            self._items.pop(repository_id, None)


class StatusService:
    """Compute, cache and persist local repository status."""

    def __init__(
        self,
        cache: StatusCache,
        *,
        ttl_seconds: int,
        remote_service: RemoteService | None = None,
        notifications: NotificationService | None = None,
    ) -> None:
        self._cache = cache
        self._ttl = max(ttl_seconds, 0)
        self._remote_service = remote_service
        self._notifications = notifications

    async def get_status(
        self,
        session: AsyncSession,
        repository: Repository,
        *,
        use_cache: bool = True,
        fetch: bool = True,
    ) -> StatusSnapshot:
        """Return status, using the memory/DB cache when it is fresh."""
        if use_cache:
            cached = self._cache.get(repository.id)
            if cached is not None:
                return cached
            row = await self._load_row(session, repository.id)
            if row is not None and self._is_fresh(row.checked_at):
                snapshot = snapshot_from_row(repository, row)
                self._cache.set(snapshot)
                return snapshot

        return await self.refresh(session, repository, fetch=fetch)

    async def refresh(
        self,
        session: AsyncSession,
        repository: Repository,
        *,
        fetch: bool = True,
    ) -> StatusSnapshot:
        """Recompute status from disk, persist it and update the cache.

        When ``fetch`` is enabled and the branch has an upstream, a best-effort
        ``git fetch --all --prune`` runs first. Fetch failures do not raise:
        ``remote_status`` becomes ``unavailable`` while ``ahead``/``behind``
        are still computed from the locally known tracking refs.
        """
        status_started = time.perf_counter()
        try:
            local = await asyncio.to_thread(read_local_status, repository.path)
        except GitStatusError as exc:
            snapshot = _error_snapshot(repository, str(exc))
            status_duration = time.perf_counter() - status_started
        else:
            ahead = local.ahead
            behind = local.behind
            remote_status = REMOTE_STATUS_STALE

            if fetch and local.upstream is not None and self._remote_service is not None:
                fetch_result = await self._remote_service.fetch(repository.path)
                if fetch_result.ok:
                    remote_status = REMOTE_STATUS_OK
                    counts = await asyncio.to_thread(
                        rev_list_counts, repository.path, local.upstream
                    )
                    if counts is not None:
                        ahead, behind = counts
                    else:
                        refreshed = await asyncio.to_thread(read_local_status, repository.path)
                        ahead, behind = refreshed.ahead, refreshed.behind
                else:
                    remote_status = REMOTE_STATUS_UNAVAILABLE

            snapshot = _snapshot_from_local(
                repository,
                local,
                ahead=ahead,
                behind=behind,
                remote_status=remote_status,
            )
            status_duration = time.perf_counter() - status_started

        await self._store(session, snapshot)
        await session.commit()
        self._cache.set(snapshot)

        logger.info(
            "status_checked",
            repository_id=repository.id,
            state=snapshot.state,
            ahead=snapshot.ahead,
            behind=snapshot.behind,
            dirty_total=snapshot.dirty.total,
        )

        duration_seconds = status_duration
        observe_status_duration(duration_seconds)
        if duration_seconds > 1.0:
            logger.warning(
                "status_slow",
                repository_id=repository.id,
                path=repository.path,
                duration_ms=round(duration_seconds * 1000, 2),
            )
        if (
            self._notifications is not None
            and snapshot.remote_status == REMOTE_STATUS_UNAVAILABLE
            and snapshot.state != "error"
        ):
            await asyncio.to_thread(
                self._notifications.notify_remote_unavailable,
                repository.id,
                repository.path,
                snapshot.error,
            )
        return snapshot

    async def _load_row(self, session: AsyncSession, repository_id: int) -> RepositoryStatus | None:
        row: RepositoryStatus | None = await session.scalar(
            select(RepositoryStatus).where(RepositoryStatus.repository_id == repository_id)
        )
        return row

    async def _store(self, session: AsyncSession, snapshot: StatusSnapshot) -> None:
        row = await self._load_row(session, snapshot.repository_id)
        if row is None:
            row = RepositoryStatus(repository_id=snapshot.repository_id, state=snapshot.state)
            session.add(row)

        row.state = snapshot.state
        row.branch = snapshot.branch
        row.head_sha = snapshot.head_sha
        row.head_subject = snapshot.head_subject
        row.head_date = snapshot.head_date
        row.upstream = snapshot.upstream
        row.ahead = snapshot.ahead
        row.behind = snapshot.behind
        row.dirty_modified = snapshot.dirty.modified
        row.dirty_staged = snapshot.dirty.staged
        row.dirty_untracked = snapshot.dirty.untracked
        row.dirty_conflicted = snapshot.dirty.conflicted
        row.detached = snapshot.detached
        row.remote_status = snapshot.remote_status
        row.error = snapshot.error
        row.checked_at = snapshot.checked_at

    def _is_fresh(self, checked_at: datetime) -> bool:
        if self._ttl <= 0:
            return False
        moment = checked_at if checked_at.tzinfo is not None else checked_at.replace(tzinfo=UTC)
        return (utcnow() - moment).total_seconds() < self._ttl


def _snapshot_from_local(
    repository: Repository,
    local: LocalStatus,
    *,
    ahead: int,
    behind: int,
    remote_status: str,
) -> StatusSnapshot:
    dirty = local.dirty
    state = classify_state(
        detached=local.detached,
        has_upstream=local.upstream is not None,
        ahead=ahead,
        behind=behind,
        dirty_total=dirty.total,
    )
    return StatusSnapshot(
        repository_id=repository.id,
        path=repository.path,
        state=state,
        branch=local.branch,
        head_sha=local.head_sha,
        head_subject=local.head_subject,
        head_date=local.head_date,
        upstream=local.upstream,
        ahead=ahead,
        behind=behind,
        dirty=dirty,
        detached=local.detached,
        remote_status=remote_status,
        error=None,
        checked_at=utcnow(),
    )


def snapshot_from_row(repository: Repository, row: RepositoryStatus) -> StatusSnapshot:
    return StatusSnapshot(
        repository_id=repository.id,
        path=repository.path,
        state=row.state,
        branch=row.branch,
        head_sha=row.head_sha,
        head_subject=row.head_subject,
        head_date=row.head_date,
        upstream=row.upstream,
        ahead=row.ahead,
        behind=row.behind,
        dirty=DirtyCounts(
            modified=row.dirty_modified,
            staged=row.dirty_staged,
            untracked=row.dirty_untracked,
            conflicted=row.dirty_conflicted,
        ),
        detached=row.detached,
        remote_status=row.remote_status,
        error=row.error,
        checked_at=row.checked_at,
    )


def _error_snapshot(repository: Repository, message: str) -> StatusSnapshot:
    return StatusSnapshot(
        repository_id=repository.id,
        path=repository.path,
        state="error",
        branch=None,
        head_sha=None,
        head_subject=None,
        head_date=None,
        upstream=None,
        ahead=0,
        behind=0,
        dirty=DirtyCounts(),
        detached=False,
        remote_status=REMOTE_STATUS_UNAVAILABLE,
        error=message,
        checked_at=utcnow(),
    )


__all__ = [
    "CANONICAL_STATES",
    "StatusCache",
    "StatusService",
    "StatusSnapshot",
    "classify_state",
    "snapshot_from_row",
]
