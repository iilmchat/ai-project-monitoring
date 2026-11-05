"""Git backend package."""

from __future__ import annotations

from app.git.command_backend import (
    CommandResult,
    FetchResult,
    fetch_all,
    rev_list_counts,
    run_git,
)
from app.git.pygit2_backend import (
    CommitInfo,
    CompareResult,
    DirtyCounts,
    GitStatusError,
    LocalStatus,
    compare_refs,
    read_commits,
    read_local_status,
)

__all__ = [
    "CommandResult",
    "CommitInfo",
    "CompareResult",
    "DirtyCounts",
    "FetchResult",
    "GitStatusError",
    "LocalStatus",
    "compare_refs",
    "fetch_all",
    "read_commits",
    "read_local_status",
    "rev_list_counts",
    "run_git",
]
