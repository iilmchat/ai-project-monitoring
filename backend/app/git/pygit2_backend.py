"""Read-only local repository status via pygit2 (ARCHITECTURE §4).

No subprocess and no mutations: the working tree, index and refs are only
inspected. All functions are synchronous; call them through
``asyncio.to_thread`` from async code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pygit2
from pygit2.enums import FileStatus

_INDEX_CHANGES = (
    FileStatus.INDEX_NEW
    | FileStatus.INDEX_MODIFIED
    | FileStatus.INDEX_DELETED
    | FileStatus.INDEX_RENAMED
    | FileStatus.INDEX_TYPECHANGE
)

_WORKTREE_CHANGES = (
    FileStatus.WT_MODIFIED
    | FileStatus.WT_DELETED
    | FileStatus.WT_RENAMED
    | FileStatus.WT_TYPECHANGE
)

_REF_PREFIXES = ("refs/remotes/", "refs/heads/")


class GitStatusError(Exception):
    """Raised when local repository status cannot be read."""


@dataclass(frozen=True, slots=True)
class DirtyCounts:
    """Counts of uncommitted changes, split by category."""

    modified: int = 0
    staged: int = 0
    untracked: int = 0
    conflicted: int = 0

    @property
    def total(self) -> int:
        return self.modified + self.staged + self.untracked + self.conflicted


@dataclass(frozen=True, slots=True)
class LocalStatus:
    """Raw snapshot read from a local repository."""

    branch: str | None
    detached: bool
    upstream: str | None
    dirty: DirtyCounts
    head_sha: str | None
    head_subject: str | None
    head_date: datetime | None
    ahead: int = 0
    behind: int = 0


def read_local_status(path: str | Path) -> LocalStatus:
    """Open the repository at ``path`` and read its status.

    Raises :class:`GitStatusError` when the path is missing or is not a valid
    Git repository (including broken ``.git`` directories).
    """
    target = Path(path)
    if not target.exists():
        raise GitStatusError(f"repository path does not exist: {target}")

    try:
        repo = pygit2.Repository(str(target))
    except (OSError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot open repository at {target}: {exc}") from exc

    try:
        unborn = repo.head_is_unborn
        detached = False if unborn else repo.head_is_detached
        branch = _branch_name(repo, detached=detached, unborn=unborn)
        upstream = _upstream_name(repo, branch) if branch and not detached else None
        head_sha, head_subject, head_date, head_oid = _head_info(repo, unborn=unborn)
        ahead, behind = _ahead_behind(repo, head_oid, upstream)
        dirty = _dirty_counts(repo)
    except (KeyError, OSError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot read repository status at {target}: {exc}") from exc

    return LocalStatus(
        branch=branch,
        detached=detached,
        upstream=upstream,
        dirty=dirty,
        head_sha=head_sha,
        head_subject=head_subject,
        head_date=head_date,
        ahead=ahead,
        behind=behind,
    )


def _branch_name(repo: pygit2.Repository, *, detached: bool, unborn: bool) -> str | None:
    if detached:
        return None
    if not unborn:
        shorthand = repo.head.shorthand
        return str(shorthand) if shorthand else None
    try:
        head_ref = repo.lookup_reference("HEAD")
    except (KeyError, pygit2.GitError):
        return None
    symbolic = head_ref.symbolic_target
    if not symbolic:
        return None
    return symbolic.rsplit("/", 1)[-1] or None


def _upstream_name(repo: pygit2.Repository, branch: str) -> str | None:
    local_branch = repo.branches.local.get(branch)
    if local_branch is None:
        return None
    try:
        raw_name = local_branch.upstream_name
    except (KeyError, pygit2.GitError):
        return None
    if not raw_name:
        return None
    name = str(raw_name)
    for prefix in _REF_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _head_info(
    repo: pygit2.Repository, *, unborn: bool
) -> tuple[str | None, str | None, datetime | None, pygit2.Oid | None]:
    if unborn:
        return None, None, None, None
    try:
        commit = repo.revparse_single("HEAD").peel(pygit2.Commit)
    except (KeyError, pygit2.GitError):
        return None, None, None, None

    subject: str | None = None
    message = commit.message or ""
    first_line = message.strip().splitlines()
    if first_line:
        subject = first_line[0]

    head_date = datetime.fromtimestamp(commit.commit_time, tz=UTC)
    return str(commit.id), subject, head_date, commit.id


def _ahead_behind(
    repo: pygit2.Repository, head_oid: pygit2.Oid | None, upstream: str | None
) -> tuple[int, int]:
    if head_oid is None or upstream is None:
        return 0, 0
    try:
        upstream_object = repo.revparse_single(upstream)
    except (KeyError, ValueError, pygit2.GitError):
        return 0, 0
    try:
        ahead, behind = repo.ahead_behind(head_oid, upstream_object.id)
    except (KeyError, ValueError, pygit2.GitError):
        return 0, 0
    return int(ahead), int(behind)


def _dirty_counts(repo: pygit2.Repository) -> DirtyCounts:
    modified = 0
    staged = 0
    untracked = 0
    conflicted = 0

    for flags in repo.status().values():
        if flags & FileStatus.CONFLICTED:
            conflicted += 1
            continue
        if flags & _INDEX_CHANGES:
            staged += 1
        if flags & FileStatus.WT_NEW:
            untracked += 1
        elif flags & _WORKTREE_CHANGES:
            modified += 1

    return DirtyCounts(
        modified=modified,
        staged=staged,
        untracked=untracked,
        conflicted=conflicted,
    )


__all__ = ["DirtyCounts", "GitStatusError", "LocalStatus", "read_local_status"]
