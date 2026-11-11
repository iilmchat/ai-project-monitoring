"""AI dashboard digest built from aggregated repository statistics (S38-001).

S43-003 adds a state-hash cache: the digest is reused only while the aggregate
statistics (and therefore the effective repository state) stay unchanged.

S60-001 enriches the LLM context with concrete repository names so the digest
can point at the projects to start with instead of only quoting counters.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.metrics import observe_ai_cache, observe_llm_call
from app.db.base import utcnow
from app.models.entities import AICache, Repository
from app.schemas.ai import DashboardAdvice
from app.services.ai_cache import build_cache_key, cache_is_fresh, cache_lock
from app.services.dependency_service import DependencyService
from app.services.llm_service import LLMService
from app.services.security_service import SecurityService

DASHBOARD_ADVICE_TTL_SECONDS = 3600
CONCURRENCY = 4
MAX_DETAIL_ITEMS = 10


def repository_display_name(repository: Repository) -> str:
    """Return the repository alias, or the last path segment as a fallback."""
    alias = (repository.alias or "").strip()
    if alias:
        return alias
    return Path(repository.path).name or repository.path


def _commits_label(count: int, language: str) -> str:
    if language == "en":
        return f"{count} commit" if count == 1 else f"{count} commits"
    if count % 10 == 1 and count % 100 != 11:
        word = "коммит"
    elif 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        word = "коммита"
    else:
        word = "коммитов"
    return f"{count} {word}"


class DashboardAdviceUnavailableError(Exception):
    """LLM is disabled/remote-blocked or returned no digest."""


class DashboardAdviceService:
    """Collect repository stats and ask the LLM for a short daily digest."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dependency_service: DependencyService,
        security_service: SecurityService,
        llm_service: LLMService,
        *,
        cache_ttl_seconds: int = DASHBOARD_ADVICE_TTL_SECONDS,
        concurrency: int = CONCURRENCY,
        prompt_version: str = "v2",
    ) -> None:
        self._session_factory = session_factory
        self._dependency_service = dependency_service
        self._security_service = security_service
        self._llm = llm_service
        self._ttl = max(cache_ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)
        self._prompt_version = prompt_version

    async def get_advice(
        self, language: str = "ru", *, refresh: bool = False
    ) -> DashboardAdvice:
        config = await self._llm.resolve()
        if not config.enabled or not self._llm.allows_remote(config):
            raise DashboardAdviceUnavailableError("llm_unavailable")

        stats, details = await self._collect_context(language)
        cache_key = build_cache_key(
            "dashboard-advice",
            language,
            {"stats": stats, "details": details},
            config.model,
            self._prompt_version,
        )

        if not refresh:
            cached = await self._read_cached(cache_key, stats)
            if cached is not None:
                observe_ai_cache("dashboard_advice", hit=True)
                return cached

        lock = cache_lock(cache_key)
        async with lock:
            if not refresh:
                cached = await self._read_cached(cache_key, stats)
                if cached is not None:
                    observe_ai_cache("dashboard_advice", hit=True)
                    return cached

            observe_ai_cache("dashboard_advice", hit=False)
            advice = await self._llm.generate_dashboard_advice(
                stats,
                details,
                language=language,
            )
            observe_llm_call(
                "dashboard_advice",
                config.provider,
                "ok" if advice is not None else "error",
            )
            if advice is None:
                raise DashboardAdviceUnavailableError("llm_unavailable")
            await self._write_cached(cache_key, config.model, advice, stats)

        return DashboardAdvice(
            advice=advice,
            cached=False,
            model=config.model,
            generated_at=utcnow(),
            stats=stats,
        )

    async def _read_cached(
        self, cache_key: str, stats: dict[str, int]
    ) -> DashboardAdvice | None:
        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is None or not cache_is_fresh(row.checked_at, self._ttl):
                return None
            payload = row.payload if isinstance(row.payload, dict) else {}
            advice = payload.get("advice")
            if not isinstance(advice, str) or not advice:
                return None
            return DashboardAdvice(
                advice=advice,
                cached=True,
                model=row.model,
                generated_at=utcnow(),
                stats=stats,
            )

    async def _write_cached(
        self,
        cache_key: str,
        model: str,
        advice: str,
        stats: dict[str, int],
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is None:
                row = AICache(
                    key=cache_key,
                    kind="dashboard_advice",
                    model=model,
                )
                session.add(row)
            row.payload = {"advice": advice, "stats": stats}
            row.checked_at = utcnow()
            await session.commit()

    async def _collect_context(
        self, language: str = "ru"
    ) -> tuple[dict[str, int], dict[str, object]]:
        """Return numeric counters plus concrete project names for the LLM."""
        async with self._session_factory() as session:
            repositories = list(
                (
                    await session.scalars(
                        select(Repository)
                        .options(selectinload(Repository.status))
                        .where(Repository.tracked.is_(True))
                        .order_by(Repository.id)
                    )
                ).all()
            )

        names = {
            repository.id: repository_display_name(repository)
            for repository in repositories
        }

        stats = {
            "repositories": len(repositories),
            "current": 0,
            "dirty": 0,
            "diverged": 0,
            "behind": 0,
            "ahead": 0,
            "no_upstream": 0,
            "outdated_packages": 0,
            "high_critical_cves": 0,
        }

        ahead_entries: list[tuple[str, int]] = []
        behind_entries: list[tuple[str, int]] = []
        dirty_names: list[str] = []
        diverged_names: list[str] = []

        for repository in repositories:
            name = names[repository.id]
            status = repository.status
            state = status.state if status is not None else "unknown"
            if state in stats:
                stats[state] += 1
            if status is not None:
                if status.ahead > 0:
                    ahead_entries.append((name, status.ahead))
                if status.behind > 0:
                    behind_entries.append((name, status.behind))
            if state == "dirty":
                dirty_names.append(name)
            elif state == "diverged":
                diverged_names.append(name)

        semaphore = asyncio.Semaphore(self._concurrency)

        async def outdated(repository: Repository) -> tuple[str, int]:
            async with semaphore:
                try:
                    report = await self._dependency_service.get_report(
                        repository.id,
                        repository.path,
                        ecosystem="all",
                    )
                except Exception:
                    return names[repository.id], 0
            return names[repository.id], report.summary.outdated

        async def vulnerabilities(
            repository: Repository,
        ) -> tuple[str, list[tuple[int, str]]]:
            async with semaphore:
                try:
                    report = await self._security_service.get_report(
                        repository.id,
                        repository.path,
                        include_secrets=False,
                        min_severity="high",
                    )
                except Exception:
                    return names[repository.id], []
            name = names[repository.id]
            findings: list[tuple[int, str]] = []
            for ecosystem in report.ecosystems:
                for vulnerability in ecosystem.vulnerabilities:
                    identifier = (
                        vulnerability.cve_ids[0]
                        if vulnerability.cve_ids
                        else vulnerability.osv_id
                    )
                    rank = 0 if vulnerability.severity == "critical" else 1
                    findings.append(
                        (
                            rank,
                            f"{identifier} в {vulnerability.package} (проект {name})",
                        )
                    )
            return name, findings

        outdated_results, vulnerability_results = await asyncio.gather(
            asyncio.gather(*(outdated(repository) for repository in repositories)),
            asyncio.gather(
                *(vulnerabilities(repository) for repository in repositories)
            ),
        )

        stats["outdated_packages"] = sum(count for _, count in outdated_results)
        stats["high_critical_cves"] = sum(
            len(findings) for _, findings in vulnerability_results
        )

        outdated_entries = sorted(
            ((name, count) for name, count in outdated_results if count > 0),
            key=lambda item: (-item[1], item[0].lower()),
        )
        cve_entries = [
            (rank, label)
            for _, findings in vulnerability_results
            for rank, label in findings
        ]
        cve_entries.sort(key=lambda item: (item[0], item[1].lower()))
        critical_cves: list[str] = []
        seen: set[str] = set()
        for _, label in cve_entries:
            if label in seen:
                continue
            seen.add(label)
            critical_cves.append(label)
            if len(critical_cves) >= MAX_DETAIL_ITEMS:
                break

        ahead_entries.sort(key=lambda item: (-item[1], item[0].lower()))
        behind_entries.sort(key=lambda item: (-item[1], item[0].lower()))

        details: dict[str, object] = {
            "repos_with_ahead": [
                f"{name} ({_commits_label(count, language)})"
                for name, count in ahead_entries[:MAX_DETAIL_ITEMS]
            ],
            "repos_with_most_outdated": [
                {"name": name, "count": count}
                for name, count in outdated_entries[:MAX_DETAIL_ITEMS]
            ],
            "critical_cves": critical_cves,
            "repos_dirty": dirty_names[:MAX_DETAIL_ITEMS],
            "repos_behind": [
                {"name": name, "commits": count}
                for name, count in behind_entries[:MAX_DETAIL_ITEMS]
            ],
            "repos_diverged": diverged_names[:MAX_DETAIL_ITEMS],
        }
        return stats, details


__all__ = ["DashboardAdviceService", "DashboardAdviceUnavailableError"]
