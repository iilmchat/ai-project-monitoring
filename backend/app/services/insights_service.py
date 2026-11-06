"""Repository insights: churn hotspots and DORA-lite commit frequency (S29)."""

from __future__ import annotations

import asyncio
import os
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from app.db.base import utcnow
from app.schemas.insights import (
    CommitFrequencyPoint,
    Hotspot,
    InsightsReport,
    InsightsStatus,
    InsightsSummary,
    InsightsWindow,
)

MAX_OUTPUT_BYTES = 8 * 1024 * 1024
HOTSPOTS_SINCE = "3 months ago"
_IGNORED_FILENAMES = frozenset(
    {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "npm-shrinkwrap.json",
        "poetry.lock",
        "pipfile.lock",
        "uv.lock",
        "cargo.lock",
        "composer.lock",
        "go.sum",
    }
)
_IGNORED_SUFFIXES = (
    ".md",
    ".lock",
    "-lock.json",
    ".min.js",
    ".min.css",
    ".map",
    ".snap",
)
_IGNORED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "vendor",
        "dist",
        "build",
        "target",
        "__pycache__",
    }
)


@dataclass(frozen=True, slots=True)
class GitCommandResult:
    """Outcome of one read-only git invocation."""

    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


class GitRunner(Protocol):
    """Injectable async git runner (tests use a fake implementation)."""

    async def __call__(
        self, args: Sequence[str], cwd: str, timeout: float
    ) -> GitCommandResult:
        """Run ``args`` in ``cwd`` and return a normalized result."""


async def run_git(
    args: Sequence[str], cwd: str, timeout: float
) -> GitCommandResult:
    """Run a read-only git command without blocking the event loop."""
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
    except OSError as exc:
        return GitCommandResult(returncode=-1, stderr=str(exc))

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return GitCommandResult(
            returncode=-1, stderr="timeout", timed_out=True
        )

    return GitCommandResult(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode("utf-8", errors="replace"),
        stderr=stderr.decode("utf-8", errors="replace"),
    )


class InsightsService:
    """Analyze a repository history for technical debt and activity."""

    def __init__(
        self,
        *,
        cache_ttl_seconds: int = 300,
        timeout_seconds: float = 10.0,
        hotspots_limit: int = 5,
        hotspots_days: int = 90,
        max_output_bytes: int = MAX_OUTPUT_BYTES,
        runner: GitRunner = run_git,
    ) -> None:
        self._ttl = max(cache_ttl_seconds, 0)
        self._timeout = max(timeout_seconds, 0.1)
        self._hotspots_limit = max(hotspots_limit, 1)
        self._hotspots_days = max(hotspots_days, 1)
        self._max_output_bytes = max(max_output_bytes, 1)
        self._runner = runner
        self._cache: dict[tuple[str, int], tuple[float, InsightsReport]] = {}

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        days: int = 30,
        refresh: bool = False,
    ) -> InsightsReport:
        """Build an insights report for one repository."""
        if not 1 <= days <= 365:
            raise ValueError(f"unsupported days: {days}")

        key = (str(Path(repo_path).resolve()), days)
        if not refresh and self._ttl > 0:
            cached = self._cache.get(key)
            if cached is not None:
                age = time.monotonic() - cached[0]
                if 0 <= age < self._ttl:
                    return cached[1].model_copy(deep=True)

        report = await self._build(repository_id, repo_path, days=days)
        self._cache[key] = (time.monotonic(), report)
        return report.model_copy(deep=True)

    async def _build(
        self, repository_id: int, repo_path: str, *, days: int
    ) -> InsightsReport:
        cwd = str(Path(repo_path))
        branch = await self._resolve_branch(cwd)
        hotspots_since = (
            HOTSPOTS_SINCE
            if self._hotspots_days == 90
            else f"{self._hotspots_days} days ago"
        )

        hotspot_args = [
            "git",
            "-C",
            cwd,
            "--no-pager",
            "log",
            "--no-merges",
            "--name-only",
            f"--since={hotspots_since}",
            "--format=",
        ]
        frequency_args = (
            [
                "git",
                "-C",
                cwd,
                "--no-pager",
                "log",
                branch,
                f"--since={days} days ago",
                "--format=%ad",
                "--date=short",
            ]
            if branch is not None
            else None
        )

        tasks = [self._runner(hotspot_args, cwd, self._timeout)]
        if frequency_args is not None:
            tasks.append(self._runner(frequency_args, cwd, self._timeout))
        results = await asyncio.gather(*tasks)
        hotspot_result = results[0]
        frequency_result = results[1] if len(results) > 1 else None

        hotspots_ok = _successful(hotspot_result, self._max_output_bytes)
        hotspots = (
            parse_hotspots(
                hotspot_result.stdout,
                repo_path,
                limit=self._hotspots_limit,
            )
            if hotspots_ok
            else []
        )

        frequency_ok = frequency_result is not None and _successful(
            frequency_result, self._max_output_bytes
        )
        until = datetime.now(UTC).date()
        since = until - timedelta(days=days - 1)
        points = (
            parse_commit_frequency(
                frequency_result.stdout,
                days=days,
                until=until,
            )
            if frequency_ok and frequency_result is not None
            else _empty_frequency(days, until)
        )
        commits = sum(point.count for point in points)

        timed_out = hotspot_result.timed_out or (
            frequency_result is not None and frequency_result.timed_out
        )
        output_too_large = _too_large(
            hotspot_result, self._max_output_bytes
        ) or (
            frequency_result is not None
            and _too_large(frequency_result, self._max_output_bytes)
        )
        shallow = is_shallow_repository(repo_path)

        status = _resolve_status(
            hotspots_ok=hotspots_ok,
            frequency_ok=frequency_ok,
            timed_out=timed_out,
            branch=branch,
            shallow=shallow,
            output_too_large=output_too_large,
        )
        error = _resolve_error(
            hotspots_ok=hotspots_ok,
            frequency_ok=frequency_ok,
            timed_out=timed_out,
            branch=branch,
            output_too_large=output_too_large,
        )
        per_day = round(commits / days, 2)
        return InsightsReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            status=status,
            window=InsightsWindow(
                days=days,
                since=since.isoformat(),
                until=until.isoformat(),
                branch=branch,
                hotspots_days=self._hotspots_days,
            ),
            hotspots=hotspots,
            commit_frequency=points,
            summary=InsightsSummary(
                commits=commits,
                per_day=per_day,
                per_week=round(per_day * 7, 2),
            ),
            error=error,
        )

    async def _resolve_branch(self, cwd: str) -> str | None:
        for candidate in ("main", "master"):
            result = await self._runner(
                [
                    "git",
                    "-C",
                    cwd,
                    "--no-pager",
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    candidate,
                ],
                cwd,
                self._timeout,
            )
            if _successful(result, self._max_output_bytes) and result.stdout.strip():
                return candidate

        result = await self._runner(
            [
                "git",
                "-C",
                cwd,
                "--no-pager",
                "rev-parse",
                "--abbrev-ref",
                "HEAD",
            ],
            cwd,
            self._timeout,
        )
        if not _successful(result, self._max_output_bytes):
            return None
        branch = result.stdout.strip()
        return branch or None


def parse_hotspots(
    output: str,
    repo_path: str,
    *,
    limit: int = 5,
) -> list[Hotspot]:
    """Count churn per file, filter noise/deleted paths and return top-N."""
    root = Path(repo_path).resolve()
    counts: Counter[str] = Counter()
    for raw_line in output.splitlines():
        path = raw_line.strip()
        if not path or not is_relevant_path(path):
            continue
        counts[path] += 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    result: list[Hotspot] = []
    for path, count in ranked:
        if not _file_exists(root, path):
            continue
        result.append(Hotspot(file=path, count=count))
        if len(result) >= max(limit, 1):
            break
    return result


def parse_commit_frequency(
    output: str,
    *,
    days: int,
    until: date | None = None,
) -> list[CommitFrequencyPoint]:
    """Group ``%ad`` dates by day and fill gaps with zeroes."""
    end = until or datetime.now(UTC).date()
    start = end - timedelta(days=days - 1)
    counts: Counter[date] = Counter()
    for raw_line in output.splitlines():
        raw = raw_line.strip()
        if not raw:
            continue
        try:
            parsed = date.fromisoformat(raw)
        except ValueError:
            continue
        counts[parsed] += 1

    return [
        CommitFrequencyPoint(
            date=(start + timedelta(days=offset)).isoformat(),
            count=counts.get(start + timedelta(days=offset), 0),
        )
        for offset in range(days)
    ]


def is_relevant_path(path: str) -> bool:
    """Return ``False`` for lock files, docs and generated/vendored paths."""
    normalized = path.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if any(part in _IGNORED_DIRS for part in parts[:-1]):
        return False
    name = parts[-1] if parts else ""
    if name in _IGNORED_FILENAMES:
        return False
    return not name.endswith(_IGNORED_SUFFIXES)


def is_shallow_repository(repo_path: str) -> bool:
    """Detect a shallow clone (``.git/shallow``)."""
    return (Path(repo_path) / ".git" / "shallow").is_file()


def _file_exists(root: Path, relative: str) -> bool:
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return False
    return candidate.is_file()


def _successful(result: GitCommandResult, max_output_bytes: int) -> bool:
    return (
        result.returncode == 0
        and not result.timed_out
        and len(result.stdout.encode("utf-8", errors="replace"))
        <= max_output_bytes
    )


def _too_large(result: GitCommandResult, max_output_bytes: int) -> bool:
    return (
        len(result.stdout.encode("utf-8", errors="replace")) > max_output_bytes
    )


def _empty_frequency(
    days: int, until: date
) -> list[CommitFrequencyPoint]:
    start = until - timedelta(days=days - 1)
    return [
        CommitFrequencyPoint(
            date=(start + timedelta(days=offset)).isoformat(),
            count=0,
        )
        for offset in range(days)
    ]


def _resolve_status(
    *,
    hotspots_ok: bool,
    frequency_ok: bool,
    timed_out: bool,
    branch: str | None,
    shallow: bool,
    output_too_large: bool,
) -> InsightsStatus:
    if timed_out:
        return "timeout"
    if not hotspots_ok and not frequency_ok:
        return "unavailable"
    if branch is None:
        return "no_branch"
    if shallow:
        return "shallow_clone"
    if not hotspots_ok or not frequency_ok or output_too_large:
        return "partial"
    return "ok"


def _resolve_error(
    *,
    hotspots_ok: bool,
    frequency_ok: bool,
    timed_out: bool,
    branch: str | None,
    output_too_large: bool,
) -> str | None:
    if timed_out:
        return "timeout"
    if output_too_large:
        return "output_too_large"
    if not hotspots_ok and not frequency_ok:
        return "git_unavailable"
    if branch is None:
        return "branch_not_found"
    if not hotspots_ok or not frequency_ok:
        return "partial"
    return None


__all__ = [
    "HOTSPOTS_SINCE",
    "MAX_OUTPUT_BYTES",
    "GitCommandResult",
    "GitRunner",
    "InsightsService",
    "is_relevant_path",
    "is_shallow_repository",
    "parse_commit_frequency",
    "parse_hotspots",
    "run_git",
]
