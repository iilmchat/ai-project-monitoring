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
    """Run ``git <args>`` in ``cwd`` without blocking the event loop."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            env=_git_env(),
        )
    except subprocess.TimeoutExpired:
        return CommandResult(
            ok=False,
            exit_code=-1,
            stdout="",
            stderr="",
            timed_out=True,
            error=f"git {' '.join(args)} timed out after {timeout:g}s",
        )
    except OSError as exc:
        return CommandResult(
            ok=False,
            exit_code=-1,
            stdout="",
            stderr=str(exc),
            error=f"failed to start git: {exc}",
        )

    ok = completed.returncode == 0
    error = None
    if not ok:
        error = completed.stderr.strip() or completed.stdout.strip() or (
            f"git exited with code {completed.returncode}"
        )
    return CommandResult(
        ok=ok,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        error=error,
    )


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
    "CommandResult",
    "FetchResult",
    "fetch_all",
    "rev_list_counts",
    "run_git",
]
