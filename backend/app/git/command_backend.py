"""Subprocess-based Git commands: fetch and rev-list (ARCHITECTURE §5).

Only read-only-for-worktree commands live here. `git fetch` updates remote
tracking refs but never touches the working tree or the index.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

FAST_STATUS_TIMEOUT = 2.0


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of a non-interactive Git command."""

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Outcome of ``git fetch --all --prune``."""

    ok: bool
    duration_ms: float
    error: str | None = None
    timed_out: bool = False


def _git_env() -> dict[str, str]:
    """Environment that prevents Git from blocking on credential prompts."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_ASKPASS", "")
    return env


def run_git(
    args: list[str],
    *,
    cwd: str | Path,
    timeout: float,
) -> CommandResult:
    """Run ``git <args>`` in ``cwd`` without blocking the event loop.

    Uses ``Popen.communicate(timeout=...)`` so that a timed-out Git process is
    explicitly killed and reaped instead of being left running (KI-001).
    """
    try:
        process: subprocess.Popen[str] = subprocess.Popen(
            ["git", *args],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=_git_env(),
        )
    except OSError as exc:
        return CommandResult(
            ok=False,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            error=f"failed to start git: {exc}",
        )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        return CommandResult(
            ok=False,
            exit_code=-1,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=True,
            error=f"git {' '.join(args)} timed out after {timeout:g}s",
        )

    ok = process.returncode == 0
    error = None
    if not ok:
        error = stderr.strip() or stdout.strip() or (
            f"git exited with code {process.returncode}"
        )
    return CommandResult(
        ok=ok,
        exit_code=process.returncode,
        stdout=stdout,
        stderr=stderr,
        error=error,
    )


def is_repo_dirty_fast(
    repository_path: str | Path,
    timeout: float = FAST_STATUS_TIMEOUT,
) -> bool:
    """Cheap dirty probe: ``git status --porcelain -uno`` (KI-002).

    ``-uno`` skips untracked files, which is what makes this fast on huge
    working trees. A timeout/error is treated as "dirty" so the caller falls
    back to the detailed pygit2 path instead of reporting a false clean state.
    """
    result = run_git(
        ["status", "--porcelain", "-uno"],
        cwd=repository_path,
        timeout=timeout,
    )
    if result.timed_out:
        logger.warning(
            "fast_status_timed_out",
            path=str(repository_path),
            timeout=timeout,
            message="Fast dirty check timed out; falling back to pygit2 status",
        )
        return True
    if not result.ok:
        return True
    return bool(result.stdout.strip())


def get_remote_url(repository_path: str | Path, remote: str = "origin") -> str | None:
    """Return the configured URL for ``remote`` (read-only, for logs)."""
    result = run_git(
        ["config", "--get", f"remote.{remote}.url"],
        cwd=repository_path,
        timeout=5,
    )
    if not result.ok:
        return None
    return result.stdout.strip() or None


def fetch_all(repository_path: str | Path, timeout: float) -> FetchResult:
    """Fetch all remotes with pruning; never raises on Git/network errors."""
    started = time.perf_counter()
    result = run_git(
        ["fetch", "--all", "--prune"],
        cwd=repository_path,
        timeout=timeout,
    )
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    return FetchResult(
        ok=result.ok,
        duration_ms=duration_ms,
        error=result.error,
        timed_out=result.timed_out,
    )


def rev_list_counts(
    repository_path: str | Path,
    upstream: str,
    head: str = "HEAD",
) -> tuple[int, int] | None:
    """Return ``(ahead, behind)`` via ``git rev-list --left-right --count``.

    ``None`` is returned when the refs cannot be resolved; callers fall back to
    pygit2 or to the local tracking refs.
    """
    result = run_git(
        ["rev-list", "--left-right", "--count", f"{head}...{upstream}"],
        cwd=repository_path,
        timeout=10,
    )
    if not result.ok:
        return None

    parts = result.stdout.split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


__all__ = [
    "FAST_STATUS_TIMEOUT",
    "CommandResult",
    "FetchResult",
    "fetch_all",
    "get_remote_url",
    "is_repo_dirty_fast",
    "rev_list_counts",
    "run_git",
]
