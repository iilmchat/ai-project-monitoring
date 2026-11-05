"""Discovery service: find local Git repositories (ARCHITECTURE §3).

Rules:
- walk each root up to ``depth`` levels below it (root itself is level 0);
- a repository is a directory containing ``.git`` (directory or gitdir file);
- never descend into ``.git``;
- skip directories whose name matches ``ignore`` (case-insensitive);
- new repositories are persisted with ``tracked=False``;
- all work is read-only: the filesystem and Git metadata are only inspected.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.models.entities import Repository, ScanRun

logger = structlog.get_logger(__name__)

GIT_MARKER = ".git"


@dataclass(slots=True)
class ScanResult:
    """Outcome of a discovery scan."""

    roots: list[str]
    depth: int
    found_count: int
    added_count: int
    skipped_count: int
    status: str
    errors: list[str] = field(default_factory=list)
    repositories: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _WalkResult:
    found: list[str]
    skipped: int
    errors: list[str]


def _normalize_ignore(ignore: list[str]) -> frozenset[str]:
    return frozenset(name.strip().lower() for name in ignore if name.strip())


def _walk_roots(roots: list[str], depth: int, ignore: list[str]) -> _WalkResult:
    """Synchronous directory walk (executed in a worker thread)."""
    ignore_names = _normalize_ignore(ignore)
    found: dict[str, None] = {}
    errors: list[str] = []
    skipped = 0

    for raw_root in roots:
        try:
            root = Path(raw_root).expanduser().resolve()
        except OSError as exc:  # pragma: no cover - exotic filesystem errors
            errors.append(f"{raw_root}: {exc}")
            continue

        if not root.is_dir():
            errors.append(f"{raw_root}: not a directory")
            continue

        # (directory, level) stack; level 0 is the root itself.
        stack: list[tuple[Path, int]] = [(root, 0)]
        while stack:
            current, level = stack.pop()

            try:
                has_git = (current / GIT_MARKER).exists()
            except OSError as exc:  # pragma: no cover - permission edge cases
                errors.append(f"{current}: {exc}")
                has_git = False

            if has_git:
                found.setdefault(str(current), None)

            if level >= depth:
                continue

            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        try:
                            if not entry.is_dir(follow_symlinks=False):
                                continue
                        except OSError as exc:  # pragma: no cover - race conditions
                            errors.append(f"{entry.path}: {exc}")
                            continue

                        name = entry.name
                        if name == GIT_MARKER:
                            # Never walk into Git internals.
                            continue
                        if name.lower() in ignore_names:
                            skipped += 1
                            continue
                        stack.append((Path(entry.path), level + 1))
            except PermissionError as exc:
                errors.append(f"{current}: permission denied ({exc})")
            except OSError as exc:
                errors.append(f"{current}: {exc}")

    return _WalkResult(found=list(found), skipped=skipped, errors=errors)


class DiscoveryService:
    """Discover repositories on disk and persist them."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def scan_directory(
        self,
        roots: list[str],
        depth: int,
        ignore: list[str],
        *,
        scan_run_id: int | None = None,
    ) -> ScanResult:
        """Scan ``roots`` and upsert repositories; optionally update a ScanRun."""
        walk = await asyncio.to_thread(_walk_roots, roots, depth, ignore)
        added_count = 0

        async with self._session_factory() as session:
            for path in walk.found:
                existing_id = await session.scalar(
                    select(Repository.id).where(Repository.path == path)
                )
                if existing_id is not None:
                    continue
                session.add(Repository(path=path, tracked=False))
                added_count += 1

            if scan_run_id is not None:
                run = await session.get(ScanRun, scan_run_id)
                if run is not None:
                    run.status = "completed"
                    run.finished_at = utcnow()
                    run.found_count = len(walk.found)
                    run.added_count = added_count
                    run.skipped_count = walk.skipped
                    run.errors = walk.errors

            await session.commit()

        result = ScanResult(
            roots=roots,
            depth=depth,
            found_count=len(walk.found),
            added_count=added_count,
            skipped_count=walk.skipped,
            status="completed",
            errors=walk.errors,
            repositories=walk.found,
        )
        logger.info(
            "scan_completed",
            scan_run_id=scan_run_id,
            roots=roots,
            depth=depth,
            found=result.found_count,
            added=result.added_count,
            skipped=result.skipped_count,
            errors=len(result.errors),
        )
        return result
