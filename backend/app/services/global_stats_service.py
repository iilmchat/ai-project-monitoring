"""Global tech-debt aggregation across tracked repositories (Sprint 63).

The service only reads data that is already produced by the local scanners
(``repository_status``, dependency cache, OSV cache) and never mutates a Git
working tree. The aggregate is cached in memory for five minutes and guarded
by a single-flight lock so a dashboard refresh cannot stampede the scanners.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.metrics import (
    observe_ai_cache,
    observe_global_stats_cache_hit,
    observe_global_stats_duration,
    observe_global_stats_partial,
    observe_llm_call,
)
from app.db.base import utcnow
from app.models.entities import AICache, Repository
from app.schemas.dependency import DependencyReport
from app.schemas.global_stats import (
    GlobalRepositoryStats,
    GlobalStatsAdvice,
    GlobalStatsPriority,
    GlobalStatsReport,
    GlobalStatsScope,
    GlobalStatsSummary,
    GlobalVulnerabilitySummary,
    ProblemTypeSummary,
    TopProblematicRepository,
)
from app.schemas.security import SecurityReport
from app.services.ai_cache import build_cache_key, cache_is_fresh, cache_lock
from app.services.dashboard_advice_service import repository_display_name
from app.services.dependency_service import DependencyService
from app.services.llm_service import LLMService
from app.services.security_service import SecurityService

DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_CONCURRENCY = 4
DEFAULT_TOP_LIMIT = 5
MAX_AI_CONTEXT_REPOSITORIES = 20
MAX_ADVICE_CHARS = 2000

_ADVICE_LABELS = {
    "ru": {
        "title": "{name}: {score} баллов",
        "cve": "Закрыть critical/high CVE и обновить затронутые пакеты.",
        "outdated": "Обновить устаревшие зависимости и прогнать тесты.",
        "dirty": "Разобрать незакоммиченные изменения.",
        "diverged": "Синхронизировать ветку с upstream.",
        "generic": "Проверить состояние репозитория и устранить найденные проблемы.",
        "reason_cve": "{count} CVE",
        "reason_outdated": "{count} устаревших пакетов",
        "reason_dirty": "{count} изменённых файлов",
        "reason_diverged": "ветка diverged",
    },
    "en": {
        "title": "{name}: score {score}",
        "cve": "Close critical/high CVEs and update the affected packages.",
        "outdated": "Update outdated dependencies and run the test suite.",
        "dirty": "Review and commit or discard the uncommitted changes.",
        "diverged": "Reconcile the branch with its upstream.",
        "generic": "Review the repository and fix the reported issues.",
        "reason_cve": "{count} CVE",
        "reason_outdated": "{count} outdated packages",
        "reason_dirty": "{count} dirty files",
        "reason_diverged": "diverged branch",
    },
}


class GlobalStatsError(Exception):
    """Base class for global stats domain errors."""


class GlobalStatsAdviceUnavailableError(GlobalStatsError):
    """The LLM is disabled, remote-blocked, or returned no report."""


@dataclass(slots=True)
class _RepositoryAccumulator:
    outdated: int = 0
    unique_outdated: set[str] = field(default_factory=set)
    vulnerabilities: GlobalVulnerabilitySummary = field(
        default_factory=GlobalVulnerabilitySummary
    )
    unique_cves: set[str] = field(default_factory=set)
    dirty_files: int = 0
    diverged: bool = False
    stale: bool = False
    dependency_ok: bool = True
    security_ok: bool = True


def problem_score(
    *,
    outdated: int,
    critical: int,
    high: int,
    medium: int,
    low: int,
    unknown: int,
    dirty_files: int,
    diverged: bool,
    iac_critical: int = 0,
    iac_high: int = 0,
    iac_medium: int = 0,
    iac_low: int = 0,
) -> int:
    """Return the deterministic tech-debt score from SPEC §3.34.1."""
    return (
        outdated
        + critical * 10
        + high * 5
        + medium * 2
        + low
        + unknown
        + dirty_files
        + (5 if diverged else 0)
        + iac_critical * 10
        + iac_high * 5
        + iac_medium * 2
        + iac_low
    )


class GlobalStatsService:
    """Build and cache a tech-debt report for all tracked repositories."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dependency_service: DependencyService,
        security_service: SecurityService,
        *,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        concurrency: int = DEFAULT_CONCURRENCY,
        top_limit: int = DEFAULT_TOP_LIMIT,
        llm_service: LLMService | None = None,
        ai_cache_ttl_seconds: int = 604800,
        prompt_version: str = "v1",
    ) -> None:
        self._session_factory = session_factory
        self._dependency_service = dependency_service
        self._security_service = security_service
        self._ttl = max(cache_ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)
        self._top_limit = max(top_limit, 1)
        self._llm_service = llm_service
        self._ai_ttl = max(ai_cache_ttl_seconds, 0)
        self._prompt_version = prompt_version
        self._cache: tuple[float, GlobalStatsReport] | None = None
        self._lock = asyncio.Lock()

    async def get_global_stats(self, *, refresh: bool = False) -> GlobalStatsReport:
        """Return the cached report, rebuilding it once after a miss."""
        if not refresh:
            cached = self._fresh_cache()
            if cached is not None:
                observe_global_stats_cache_hit()
                cached.cached = True
                return cached

        async with self._lock:
            if not refresh:
                cached = self._fresh_cache()
                if cached is not None:
                    observe_global_stats_cache_hit()
                    cached.cached = True
                    return cached

            started = time.monotonic()
            report = await self._build()
            observe_global_stats_duration(time.monotonic() - started)
            observe_global_stats_partial(
                report.error is not None or bool(report.errors)
            )
            self._cache = (time.monotonic(), report)
            return report.model_copy(deep=True).model_copy(deep=True)

    def _fresh_cache(self) -> GlobalStatsReport | None:
        if self._ttl <= 0 or self._cache is None:
            return None
        cached_at, report = self._cache
        if 0 <= time.monotonic() - cached_at < self._ttl:
            return report.model_copy(deep=True)
        return None

    async def _build(self) -> GlobalStatsReport:
        async with self._session_factory() as session:
            total_repositories = await session.scalar(
                select(func.count(Repository.id))
            )
            repositories = list(
                (
                    await session.scalars(
                        select(Repository)
                        .options(selectinload(Repository.status))
                        .where(Repository.tracked.is_(True))
                        .order_by(Repository.path)
                    )
                ).all()
            )

        semaphore = asyncio.Semaphore(self._concurrency)

        async def collect(
            repository: Repository,
        ) -> tuple[Repository, _RepositoryAccumulator, list[str]]:
            name = repository_display_name(repository)
            accumulator = _RepositoryAccumulator()
            errors: list[str] = []
            async with semaphore:
                try:
                    dependency_report = await self._dependency_service.get_report(
                        repository.id,
                        repository.path,
                        ecosystem="all",
                    )
                except Exception:
                    dependency_report = None
                try:
                    security_report = await self._security_service.get_report(
                        repository.id,
                        repository.path,
                        include_secrets=False,
                        min_severity="all",
                    )
                except Exception:
                    security_report = None

            if dependency_report is None:
                accumulator.dependency_ok = False
            else:
                _apply_dependency_report(accumulator, dependency_report)
            if security_report is None:
                accumulator.security_ok = False
            else:
                _apply_security_report(accumulator, security_report)

            if not accumulator.dependency_ok and not accumulator.security_ok:
                errors.append(f"{name}: all_sources_unavailable")
            elif not accumulator.dependency_ok:
                errors.append(f"{name}: dependencies_unavailable")
            elif not accumulator.security_ok:
                errors.append(f"{name}: security_unavailable")
            return repository, accumulator, errors

        results = await asyncio.gather(
            *(collect(repository) for repository in repositories)
        )

        global_unique_outdated: set[str] = set()
        global_unique_cves: set[str] = set()
        vulnerabilities = GlobalVulnerabilitySummary()
        dirty_files = 0
        diverged_branches = 0
        outdated_total = 0
        repository_rows: list[GlobalRepositoryStats] = []
        errors: list[str] = []
        scanned = 0

        for repository, accumulator, repository_errors in results:
            errors.extend(repository_errors)
            dirty = _dirty_files(repository)
            accumulator.dirty_files = dirty
            accumulator.diverged = (
                repository.status is not None
                and repository.status.state == "diverged"
            )
            if accumulator.dependency_ok or accumulator.security_ok:
                scanned += 1
                if not accumulator.dependency_ok or not accumulator.security_ok:
                    status = "partial"
                else:
                    status = "ok"
            else:
                status = "error"

            score = problem_score(
                outdated=accumulator.outdated,
                critical=accumulator.vulnerabilities.critical,
                high=accumulator.vulnerabilities.high,
                medium=accumulator.vulnerabilities.medium,
                low=accumulator.vulnerabilities.low,
                unknown=accumulator.vulnerabilities.unknown,
                dirty_files=dirty,
                diverged=accumulator.diverged,
            )
            repository_rows.append(
                GlobalRepositoryStats(
                    repository_id=repository.id,
                    name=repository_display_name(repository),
                    path=repository.path,
                    status=status,
                    stale=accumulator.stale,
                    outdated_packages=accumulator.outdated,
                    vulnerabilities=accumulator.vulnerabilities,
                    dirty_files=dirty,
                    diverged=accumulator.diverged,
                    iac_issues=0,
                    problem_score=score,
                    error=repository_errors[0] if repository_errors else None,
                )
            )

            outdated_total += accumulator.outdated
            global_unique_outdated.update(accumulator.unique_outdated)
            global_unique_cves.update(accumulator.unique_cves)
            dirty_files += dirty
            if accumulator.diverged:
                diverged_branches += 1
            vulnerabilities = _add_vulnerabilities(
                vulnerabilities, accumulator.vulnerabilities
            )

        repository_rows.sort(
            key=lambda item: (-item.problem_score, item.name.lower())
        )
        vulnerabilities.unique_cves = len(global_unique_cves)
        vulnerabilities.total = (
            vulnerabilities.critical
            + vulnerabilities.high
            + vulnerabilities.medium
            + vulnerabilities.low
            + vulnerabilities.unknown
        )

        tracked = len(repositories)
        skipped = tracked - scanned
        partial = bool(errors)
        summary = GlobalStatsSummary(
            outdated_packages=outdated_total,
            unique_outdated_packages=len(global_unique_outdated),
            vulnerabilities=vulnerabilities,
            dirty_files=dirty_files,
            diverged_branches=diverged_branches,
            iac_issues=0,
            problem_types=[
                ProblemTypeSummary(
                    type="outdated_packages",
                    count=outdated_total,
                    severity="medium",
                ),
                ProblemTypeSummary(
                    type="vulnerabilities",
                    count=vulnerabilities.total,
                    severity="high",
                ),
                ProblemTypeSummary(
                    type="dirty_files",
                    count=dirty_files,
                    severity="medium",
                ),
                ProblemTypeSummary(
                    type="diverged_branches",
                    count=diverged_branches,
                    severity="high",
                ),
                ProblemTypeSummary(
                    type="iac_issues",
                    count=0,
                    severity="low",
                ),
            ],
        )

        return GlobalStatsReport(
            checked_at=utcnow(),
            cached=False,
            scope=GlobalStatsScope(
                repositories=int(total_repositories or 0),
                tracked=tracked,
                scanned=scanned,
                skipped=skipped,
            ),
            summary=summary,
            repositories=repository_rows,
            top_problematic=[
                TopProblematicRepository(
                    repository_id=item.repository_id,
                    name=item.name,
                    problem_score=item.problem_score,
                )
                for item in repository_rows
                if item.problem_score > 0
            ][: self._top_limit],
            errors=errors,
            error=(
                "all_sources_unavailable"
                if tracked > 0 and scanned == 0
                else ("partial_data" if partial else None)
            ),
        )

    async def get_ai_advice(
        self,
        language: str = "ru",
        *,
        refresh: bool = False,
    ) -> GlobalStatsAdvice:
        """Return a cached or freshly generated Markdown tech-debt report."""
        report = await self.get_global_stats()
        llm = self._llm_service
        if llm is None:
            raise GlobalStatsAdviceUnavailableError("llm_unavailable")
        config = await llm.resolve()
        if not config.enabled or not llm.allows_remote(config):
            raise GlobalStatsAdviceUnavailableError("llm_unavailable")

        state = _advice_state(report)
        cache_key = build_cache_key(
            "global-stats-advice",
            language,
            state,
            config.model,
            self._prompt_version,
        )

        if not refresh:
            cached = await self._read_cached(cache_key)
            if cached is not None:
                observe_ai_cache("global_stats_advice", hit=True)
                return cached

        lock = cache_lock(cache_key)
        async with lock:
            if not refresh:
                cached = await self._read_cached(cache_key)
                if cached is not None:
                    observe_ai_cache("global_stats_advice", hit=True)
                    return cached

            observe_ai_cache("global_stats_advice", hit=False)
            advice = await llm.generate_global_stats_advice(
                state, language=language
            )
            observe_llm_call(
                "global_stats_advice",
                config.provider,
                "ok" if advice is not None else "error",
            )
            if advice is None:
                raise GlobalStatsAdviceUnavailableError("llm_unavailable")
            advice = advice[:MAX_ADVICE_CHARS]
            priorities = _priorities(report, language)
            await self._write_cached(
                cache_key,
                config.model,
                advice,
                priorities,
            )

        return GlobalStatsAdvice(
            generated_at=utcnow(),
            summary=advice,
            priorities=priorities,
            model=config.model,
            cached=False,
        )

    async def _read_cached(self, cache_key: str) -> GlobalStatsAdvice | None:
        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is None or not cache_is_fresh(row.checked_at, self._ai_ttl):
                return None
            payload = row.payload if isinstance(row.payload, dict) else {}
            advice = payload.get("advice")
            if not isinstance(advice, str) or not advice:
                return None
            raw_priorities = payload.get("priorities")
            priorities: list[GlobalStatsPriority] = []
            if isinstance(raw_priorities, list):
                for item in raw_priorities:
                    if not isinstance(item, dict):
                        continue
                    try:
                        priorities.append(GlobalStatsPriority.model_validate(item))
                    except ValueError:
                        continue
            return GlobalStatsAdvice(
                generated_at=utcnow(),
                summary=advice,
                priorities=priorities,
                model=row.model,
                cached=True,
            )

    async def _write_cached(
        self,
        cache_key: str,
        model: str,
        advice: str,
        priorities: list[GlobalStatsPriority],
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is None:
                row = AICache(
                    key=cache_key,
                    kind="global_stats_advice",
                    model=model,
                )
                session.add(row)
            row.payload = {
                "advice": advice,
                "priorities": [
                    item.model_dump(mode="json") for item in priorities
                ],
            }
            row.checked_at = utcnow()
            await session.commit()


def _apply_dependency_report(
    accumulator: _RepositoryAccumulator,
    report: DependencyReport,
) -> None:
    for ecosystem in report.ecosystems:
        if ecosystem.status == "unavailable":
            accumulator.dependency_ok = False
        if ecosystem.source in {"stale_cache", "none"}:
            accumulator.stale = True
        for package in ecosystem.packages:
            if package.status != "outdated":
                continue
            accumulator.outdated += 1
            accumulator.unique_outdated.add(f"{ecosystem.ecosystem}:{package.name}")


def _apply_security_report(
    accumulator: _RepositoryAccumulator,
    report: SecurityReport,
) -> None:
    if report.status == "unavailable":
        accumulator.security_ok = False
    for ecosystem in report.ecosystems:
        if ecosystem.status == "unavailable":
            accumulator.security_ok = False
    accumulator.vulnerabilities = GlobalVulnerabilitySummary(
        critical=report.summary.critical,
        high=report.summary.high,
        medium=report.summary.medium,
        low=report.summary.low,
        unknown=report.summary.unknown,
        total=report.summary.critical
        + report.summary.high
        + report.summary.medium
        + report.summary.low
        + report.summary.unknown,
        unique_cves=0,
    )
    for ecosystem in report.ecosystems:
        for vulnerability in ecosystem.vulnerabilities:
            if vulnerability.cve_ids:
                accumulator.unique_cves.update(vulnerability.cve_ids)
            else:
                accumulator.unique_cves.add(vulnerability.osv_id)


def _add_vulnerabilities(
    left: GlobalVulnerabilitySummary,
    right: GlobalVulnerabilitySummary,
) -> GlobalVulnerabilitySummary:
    return GlobalVulnerabilitySummary(
        critical=left.critical + right.critical,
        high=left.high + right.high,
        medium=left.medium + right.medium,
        low=left.low + right.low,
        unknown=left.unknown + right.unknown,
        total=left.total + right.total,
        unique_cves=left.unique_cves + right.unique_cves,
    )


def _dirty_files(repository: Repository) -> int:
    status = repository.status
    if status is None:
        return 0
    return (
        status.dirty_modified
        + status.dirty_staged
        + status.dirty_untracked
        + status.dirty_conflicted
    )


def _advice_state(report: GlobalStatsReport) -> dict[str, object]:
    return {
        "summary": report.summary.model_dump(mode="json"),
        "top_problematic": [
            item.model_dump(mode="json") for item in report.top_problematic
        ],
        "repositories": [
            {
                "name": item.name,
                "problem_score": item.problem_score,
                "outdated_packages": item.outdated_packages,
                "vulnerabilities": item.vulnerabilities.total,
                "dirty_files": item.dirty_files,
                "diverged": item.diverged,
                "iac_issues": item.iac_issues,
            }
            for item in report.repositories[:MAX_AI_CONTEXT_REPOSITORIES]
        ],
    }


def _priorities(
    report: GlobalStatsReport,
    language: str,
) -> list[GlobalStatsPriority]:
    labels = _ADVICE_LABELS["en" if language == "en" else "ru"]
    by_id = {item.repository_id: item for item in report.repositories}
    priorities: list[GlobalStatsPriority] = []
    for top in report.top_problematic:
        repository = by_id.get(top.repository_id)
        if repository is None:
            continue
        reasons: list[str] = []
        if repository.vulnerabilities.critical + repository.vulnerabilities.high > 0:
            reasons.append(
                labels["reason_cve"].format(
                    count=repository.vulnerabilities.critical
                    + repository.vulnerabilities.high
                )
            )
            action = labels["cve"]
        elif repository.outdated_packages > 0:
            reasons.append(
                labels["reason_outdated"].format(
                    count=repository.outdated_packages
                )
            )
            action = labels["outdated"]
        elif repository.dirty_files > 0:
            reasons.append(
                labels["reason_dirty"].format(count=repository.dirty_files)
            )
            action = labels["dirty"]
        elif repository.diverged:
            reasons.append(labels["reason_diverged"])
            action = labels["diverged"]
        else:
            action = labels["generic"]
        if (
            repository.diverged
            and repository.vulnerabilities.high == 0
            and labels["reason_diverged"] not in reasons
        ):
            reasons.append(labels["reason_diverged"])
        priorities.append(
            GlobalStatsPriority(
                title=labels["title"].format(
                    name=repository.name,
                    score=repository.problem_score,
                ),
                reason=", ".join(reasons) if reasons else action,
                repository_id=repository.repository_id,
                action=action,
            )
        )
    return priorities


__all__ = [
    "GlobalStatsAdviceUnavailableError",
    "GlobalStatsError",
    "GlobalStatsService",
    "problem_score",
]
