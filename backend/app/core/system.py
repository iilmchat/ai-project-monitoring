"""Small runtime helpers shared by the app factory and health endpoint."""

from __future__ import annotations

import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def read_git_version() -> str | None:
    """Return ``git --version`` output; executed once per process."""
    try:
        completed = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


__all__ = ["read_git_version"]
