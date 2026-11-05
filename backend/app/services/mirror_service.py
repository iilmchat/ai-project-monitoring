"""Mirror GitHub ↔ GitFlic service (SPEC §3.8, ARCHITECTURE §7)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.metrics import observe_mirror_check_duration
from app.db.base import utcnow
from app.models.entities import Repository, RepositoryMirrorStatus, RepositoryStatus
from app.providers.base import BranchResult
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient
from app.services.recommendation_service import Recommendation

logger = structlog.get_logger(__name__)

CANONICAL_PROVIDERS = frozenset({"github", "gitflic", "both"})
IN_SYNC = "in_sync"
NOT_APPLICABLE = "not_applicable"
UNAVAILABLE = "unavailable"
MISSING_ON_GITFLIC = "missing_on_gitflic"
MISSING_ON_GITHUB = "missing_on_github"
BEHIND_GITFLIC = "behind_gitflic"
BEHIND_GITHUB = "behind_github"
DIVERGED = "diverged"
HISTORY_REWRITTEN = "history_rewritten"

MIRROR_STATUSES = frozenset(
    {
        IN_SYNC,
        NOT_APPLICABLE,
        UNAVAILABLE,
        MISSING_ON_GITFLIC,
        MISSING_ON_GITHUB,
        BEHIND_GITFLIC,
        BEHIND_GITHUB,
        DIVERGED,
        HISTORY_REWRITTEN,
    }
)

ATTENTION_STATUSES = frozenset(
    {
        MISSING_ON_GITFLIC,
        MISSING_ON_GITHUB,
        BEHIND_GITFLIC,
        BEHIND_GITHUB,
        DIVERGED,
        HISTORY_REWRITTEN,
    }
)


@dataclass(frozen=True, slots=True)
class MirrorProviderInfo:
    full_name: str | None
    branch: str | None
    head_sha: str | None
    head_date: datetime | None
    private: bool | None
    checked_at: datetime | None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MirrorSnapshot:
    repository_id: int
    mirror_status: str
    canonical_provider: str
    mirror_expected: bool
    github: MirrorProviderInfo | None
    gitflic: MirrorProviderInfo | None
    recommendations: list[Recommendation] = field(default_factory=list)
    checked_at: datetime = field(default_factory=utcnow)


def classify_mirror_status(
    github: BranchResult | None,
    gitflic: BranchResult | None,
    *,
    canonical_provider: str,
    mirror_expected: bool,
) -> str:
    """Classify GitHub ↔ GitFlic consistency.

    ``None`` means the provider is not configured for this repository. When
    SHAs differ, classification is a deterministic heuristic based on branch
    commit dates (full history comparison arrives with provider Compare API).
    """
    if not mirror_expected:
        return NOT_APPLICABLE
    if github is None and gitflic is None:
        return UNAVAILABLE
    if github is None:
        if gitflic is None or not gitflic.available:
            return UNAVAILABLE
        return MISSING_ON_GITHUB
    if gitflic is None:
        if not github.available:
            return UNAVAILABLE
        return MISSING_ON_GITFLIC

    if github.error is not None or gitflic.error is not None:
        return UNAVAILABLE
    if not github.found:
        return MISSING_ON_GITHUB if gitflic.available else UNAVAILABLE
    if not gitflic.found:
        return MISSING_ON_GITFLIC if github.available else UNAVAILABLE

    if github.sha is None or gitflic.sha is None:
        return UNAVAILABLE
    if github.sha == gitflic.sha:
        return IN_SYNC

    gh_date = github.date
    gf_date = gitflic.date
    if canonical_provider == "github":
        if gh_date is not None and gf_date is not None:
            if gf_date < gh_date:
                return BEHIND_GITFLIC
            if gf_date > gh_date:
                return HISTORY_REWRITTEN
        return DIVERGED
    if canonical_provider == "gitflic":
        if gh_date is not None and gf_date is not None:
            if gh_date < gf_date:
                return BEHIND_GITHUB
            if gh_date > gf_date:
                return HISTORY_REWRITTEN
        return DIVERGED
    # canonical = both: newer side is the reference.
    if gh_date is not None and gf_date is not None and gh_date != gf_date:
        return BEHIND_GITFLIC if gh_date > gf_date else BEHIND_GITHUB
    return DIVERGED


def _mirror_recommendations(
    status: str,
    *,
    branch: str,
) -> list[Recommendation]:
    if status == MISSING_ON_GITFLIC:
        return [
            Recommendation(
                action="create-mirror",
                reason="Репозиторий отсутствует в GitFlic.",
                command=f"git push gitflic {branch}",
                category="mirror",
            )
        ]
    if status == MISSING_ON_GITHUB:
        return [
            Recommendation(
                action="create-mirror",
                reason="Репозиторий отсутствует в GitHub.",
                command=f"git push origin {branch}",
                category="mirror",
            )
        ]
    if status == BEHIND_GITFLIC:
        return [
            Recommendation(
                action="push-mirror",
                reason="Зеркало GitFlic отстаёт от канонического GitHub.",
                command=f"git push gitflic {branch}",
                category="mirror",
            )
        ]
    if status == BEHIND_GITHUB:
        return [
            Recommendation(
                action="push-mirror",
                reason="GitHub отстаёт от канонического GitFlic.",
                command=f"git push origin {branch}",
                category="mirror",
            )
        ]
    if status == DIVERGED:
        return [
            Recommendation(
                action="review-mirror",
                reason="Истории разошлись: требуется ручная сверка перед синхронизацией.",
                command="git log --oneline --left-right origin/main...gitflic/main",
                category="mirror",
            )
        ]
    if status == HISTORY_REWRITTEN:
        return [
            Recommendation(
                action="manual-review",
                reason="Похоже на force-push/переписанную историю в одном из провайдеров.",
                command="git log --oneline --graph --all --decorate",
                category="mirror",
            )
        ]
    return []


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _provider_info(
    full_name: str | None,
    branch: str,
    result: BranchResult | None,
    checked_at: datetime,
) -> MirrorProviderInfo | None:
    if full_name is None:
        return None
    return MirrorProviderInfo(
        full_name=full_name,
        branch=branch,
        head_sha=result.sha if result else None,
        head_date=result.date if result else None,
        private=None,
        checked_at=checked_at,
        error=result.error if result else "not_queried",
    )


def _details(
    github: MirrorProviderInfo | None,
    gitflic: MirrorProviderInfo | None,
    github_result: BranchResult | None,
    gitflic_result: BranchResult | None,
) -> dict[str, Any]:
    def side(info: MirrorProviderInfo | None, result: BranchResult | None) -> dict[str, Any]:
        if info is None:
            return {"full_name": None, "configured": False}
        return {
            "full_name": info.full_name,
            "branch": info.branch,
            "head_sha": info.head_sha,
            "head_date": _iso(info.head_date),
            "checked_at": _iso(info.checked_at),
            "found": result.found if result else False,
            "error": result.error if result else None,
            "rate_limited": result.rate_limited if result else False,
        }

    return {
        "github": side(github, github_result),
        "gitflic": side(gitflic, gitflic_result),
        "classification": "sha+date-heuristic",
    }


class MirrorService:
    """Compute, persist and cache cross-provider mirror status."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        github: GitHubClient,
        gitflic: GitFlicClient,
        *,
        ttl_seconds: int = 300,
    ) -> None:
        self._session_factory = session_factory
        self._github = github
        self._gitflic = gitflic
        self._ttl = max(ttl_seconds, 0)

    @property
    def enabled(self) -> bool:
        return self._github.configured or self._gitflic.configured

    async def get_mirror_status(
        self,
        repository: Repository,
        *,
        refresh: bool = False,
    ) -> MirrorSnapshot:
        if not refresh:
            async with self._session_factory() as session:
                row = await self._load_row(session, repository.id)
            if row is not None and self._is_fresh(row.checked_at):
                return snapshot_from_row(repository, row)
        return await self.refresh_mirror_status(repository)

    async def refresh_mirror_status(self, repository: Repository) -> MirrorSnapshot:
        started = time.perf_counter()
        branch = await self._local_branch(repository)

        github_result, gitflic_result = await asyncio.gather(
            self._lookup(self._github, repository.github_full_name, branch),
            self._lookup(self._gitflic, repository.gitflic_full_name, branch),
        )

        checked_at = utcnow()
        github_info = _provider_info(
            repository.github_full_name, branch, github_result, checked_at
        )
        gitflic_info = _provider_info(
            repository.gitflic_full_name, branch, gitflic_result, checked_at
        )
        mirror_status = classify_mirror_status(
            github_result,
            gitflic_result,
            canonical_provider=repository.canonical_provider,
            mirror_expected=repository.mirror_expected,
        )
        snapshot = MirrorSnapshot(
            repository_id=repository.id,
            mirror_status=mirror_status,
            canonical_provider=repository.canonical_provider,
            mirror_expected=repository.mirror_expected,
            github=github_info,
            gitflic=gitflic_info,
            recommendations=_mirror_recommendations(mirror_status, branch=branch),
            checked_at=checked_at,
        )

        details = _details(github_info, gitflic_info, github_result, gitflic_result)
        async with self._session_factory() as session:
            row = await self._load_row(session, repository.id)
            if row is None:
                row = RepositoryMirrorStatus(repository_id=repository.id)
                session.add(row)
            row.github_head_sha = github_info.head_sha if github_info else None
            row.gitflic_head_sha = gitflic_info.head_sha if gitflic_info else None
            row.github_branch = github_info.branch if github_info else None
            row.gitflic_branch = gitflic_info.branch if gitflic_info else None
            row.github_checked_at = github_info.checked_at if github_info else None
            row.gitflic_checked_at = gitflic_info.checked_at if gitflic_info else None
            row.mirror_status = mirror_status
            row.details = details
            row.checked_at = checked_at
            await session.commit()

        duration = time.perf_counter() - started
        observe_mirror_check_duration(duration)
        logger.info(
            "mirror_checked",
            repository_id=repository.id,
            mirror_status=mirror_status,
            duration_ms=round(duration * 1000, 2),
        )
        return snapshot

    async def discover_candidates(self) -> dict[str, list[dict[str, object]]]:
        github_repos, gitflic_repos = await asyncio.gather(
            self._github.list_repos(),
            self._gitflic.list_repos(),
        )

        unknown: list[dict[str, object]] = []
        if not self._github.configured:
            unknown.append({"provider": "github", "reason": "not_configured"})
        if not self._gitflic.configured:
            unknown.append({"provider": "gitflic", "reason": "not_configured"})

        github_by_name = {
            str(item["full_name"]).rsplit("/", 1)[-1].lower(): item
            for item in github_repos
        }
        gitflic_by_name = {
            str(item["full_name"]).rsplit("/", 1)[-1].lower(): item for item in gitflic_repos
        }

        github_only = [
            {
                **item,
                "canonical_provider_guess": "github",
                "suggested_action": "create-mirror",
            }
            for name, item in github_by_name.items()
            if name not in gitflic_by_name
        ]
        gitflic_only = [
            {
                **item,
                "canonical_provider_guess": "gitflic",
                "suggested_action": "create-mirror",
            }
            for name, item in gitflic_by_name.items()
            if name not in github_by_name
        ]
        both = [
            {
                "provider": "both",
                "full_name": github_by_name[name]["full_name"],
                "gitflic_full_name": gitflic_by_name[name]["full_name"],
                "private": bool(github_by_name[name].get("private", False)),
                "canonical_provider_guess": "github",
                "suggested_action": "verify-history",
            }
            for name in github_by_name.keys() & gitflic_by_name.keys()
        ]
        return {
            "github_only": github_only,
            "gitflic_only": gitflic_only,
            "both": both,
            "unknown": unknown,
        }

    async def invalidate(self, repository_id: int) -> None:
        async with self._session_factory() as session:
            row = await self._load_row(session, repository_id)
            if row is not None:
                await session.delete(row)
                await session.commit()

    async def _lookup(
        self,
        client: GitHubClient | GitFlicClient,
        full_name: str | None,
        branch: str,
    ) -> BranchResult | None:
        if full_name is None:
            return None
        return await client.get_branch(full_name, branch)

    async def _local_branch(self, repository: Repository) -> str:
        async with self._session_factory() as session:
            row = await session.scalar(
                select(RepositoryStatus).where(
                    RepositoryStatus.repository_id == repository.id
                )
            )
        return row.branch if row is not None and row.branch else "main"

    async def _load_row(
        self, session: AsyncSession, repository_id: int
    ) -> RepositoryMirrorStatus | None:
        row: RepositoryMirrorStatus | None = await session.scalar(
            select(RepositoryMirrorStatus).where(
                RepositoryMirrorStatus.repository_id == repository_id
            )
        )
        return row

    def _is_fresh(self, checked_at: datetime) -> bool:
        if self._ttl <= 0:
            return False
        moment = checked_at if checked_at.tzinfo is not None else checked_at.replace(tzinfo=UTC)
        return (utcnow() - moment).total_seconds() < self._ttl


def snapshot_from_row(
    repository: Repository, row: RepositoryMirrorStatus
) -> MirrorSnapshot:
    details = row.details or {}

    def side(key: str, full_name: str | None) -> MirrorProviderInfo | None:
        data = details.get(key) or {}
        name = data.get("full_name") or full_name
        if name is None:
            return None
        return MirrorProviderInfo(
            full_name=str(name),
            branch=data.get("branch"),
            head_sha=data.get("head_sha"),
            head_date=_parse_iso(data.get("head_date")),
            private=None,
            checked_at=_parse_iso(data.get("checked_at")),
            error=_optional_str(data.get("error")),
        )

    return MirrorSnapshot(
        repository_id=repository.id,
        mirror_status=row.mirror_status,
        canonical_provider=repository.canonical_provider,
        mirror_expected=repository.mirror_expected,
        github=side("github", repository.github_full_name),
        gitflic=side("gitflic", repository.gitflic_full_name),
        recommendations=_mirror_recommendations(
            row.mirror_status,
            branch=(row.github_branch or row.gitflic_branch or "main"),
        ),
        checked_at=row.checked_at,
    )


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def count_mirror_issues(rows: Iterable[RepositoryMirrorStatus]) -> int:
    return sum(1 for row in rows if row.mirror_status in ATTENTION_STATUSES)


__all__ = [
    "ATTENTION_STATUSES",
    "CANONICAL_PROVIDERS",
    "MIRROR_STATUSES",
    "MirrorProviderInfo",
    "MirrorService",
    "MirrorSnapshot",
    "classify_mirror_status",
    "count_mirror_issues",
    "snapshot_from_row",
]
