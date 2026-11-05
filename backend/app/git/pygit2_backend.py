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
from pygit2.enums import FileStatus, SortMode

from app.git.command_backend import is_repo_dirty_fast

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


@dataclass(frozen=True, slots=True)
class CommitInfo:
    """Single commit metadata (SPEC §3.5)."""

    sha: str
    subject: str
    author: str
    date: datetime


@dataclass(frozen=True, slots=True)
class CompareResult:
    """Comparison between two refs (SPEC §3.5)."""

    ahead: int
    behind: int
    status: str
    commits: list[CommitInfo]


def _open_repository(path: str | Path) -> pygit2.Repository:
    target = Path(path)
    if not target.exists():
        raise GitStatusError(f"repository path does not exist: {target}")
    try:
        return pygit2.Repository(str(target))
    except (OSError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot open repository at {target}: {exc}") from exc


def read_local_status(path: str | Path) -> LocalStatus:
    """Open the repository at ``path`` and read its status.

    Raises :class:`GitStatusError` when the path is missing or is not a valid
    Git repository (including broken ``.git`` directories).
    """
    target = Path(path)
    repo = _open_repository(target)

    try:
        unborn = repo.head_is_unborn
        detached = False if unborn else repo.head_is_detached
        branch = _branch_name(repo, detached=detached, unborn=unborn)
        upstream = _upstream_name(repo, branch) if branch and not detached else None
        head_sha, head_subject, head_date, head_oid = _head_info(repo, unborn=unborn)
        ahead, behind = _ahead_behind(repo, head_oid, upstream)
        dirty = _dirty_counts(repo, target)
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


def _dirty_counts(repo: pygit2.Repository, path: str | Path) -> DirtyCounts:
    # KI-002: avoid a full working-tree walk when tracked files are clean.
    if not is_repo_dirty_fast(path):
        return DirtyCounts()

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


def _commit_info(commit: pygit2.Commit) -> CommitInfo:
    message = str(commit.message or "")
    lines = message.strip().splitlines()
    subject = lines[0] if lines else ""
    author = str(commit.author.name or "")
    date = datetime.fromtimestamp(commit.author.time, tz=UTC)
    return CommitInfo(sha=str(commit.id), subject=subject, author=author, date=date)


def read_commits(path: str | Path, rev: str = "HEAD", limit: int = 20) -> list[CommitInfo]:
    """Return up to ``limit`` newest commits reachable from ``rev``."""
    repo = _open_repository(path)
    if limit <= 0:
        return []
    try:
        start = repo.revparse_single(rev).peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot resolve {rev!r} in {path}: {exc}") from exc

    commits: list[CommitInfo] = []
    for commit in repo.walk(start.id, SortMode.TIME):
        commits.append(_commit_info(commit))
        if len(commits) >= limit:
            break
    return commits


def compare_refs(
    path: str | Path,
    base: str,
    head: str = "HEAD",
    limit: int = 10,
) -> CompareResult:
    """Compare ``head`` against ``base`` (both within the same repository)."""
    repo = _open_repository(path)
    try:
        base_commit = repo.revparse_single(base).peel(pygit2.Commit)
        head_commit = repo.revparse_single(head).peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot resolve refs {base!r}..{head!r}: {exc}") from exc

    try:
        ahead, behind = repo.ahead_behind(head_commit.id, base_commit.id)
    except (KeyError, ValueError, pygit2.GitError) as exc:
        raise GitStatusError(f"cannot compare {base!r}..{head!r}: {exc}") from exc

    ahead_count = int(ahead)
    behind_count = int(behind)
    if ahead_count and behind_count:
        status = "diverged"
    elif ahead_count:
        status = "ahead"
    elif behind_count:
        status = "behind"
    else:
        status = "identical"

    commits: list[CommitInfo] = []
    if ahead_count > 0 and limit > 0:
        walker = repo.walk(head_commit.id, SortMode.TIME)
        walker.hide(base_commit.id)
        for commit in walker:
            commits.append(_commit_info(commit))
            if len(commits) >= limit:
                break

    return CompareResult(
        ahead=ahead_count,
        behind=behind_count,
        status=status,
        commits=commits,
    )


__all__ = [
    "CommitInfo",
    "CompareResult",
    "DirtyCounts",
    "GitStatusError",
    "LocalStatus",
    "compare_refs",
    "read_commits",
    "read_local_status",
]

