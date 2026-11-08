"""AI dashboard digest built from aggregated repository statistics (S38-001).

S43-003 adds a state-hash cache: the digest is reused only while the aggregate
statistics (and therefore the effective repository state) stay unchanged.
"""

from __future__ import annotations

import asyncio

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
        prompt_version: str = "v1",
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

        stats = await self._collect_stats()
        cache_key = build_cache_key(
            "dashboard-advice",
            language,
            stats,
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

    async def _collect_stats(self) -> dict[str, int]:
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
        for repository in repositories:
            state = repository.status.state if repository.status is not None else "unknown"
            if state in stats:
                stats[state] += 1

        semaphore = asyncio.Semaphore(self._concurrency)

        async def outdated(repository: Repository) -> int:
            async with semaphore:
                try:
                    report = await self._dependency_service.get_report(
                        repository.id,
                        repository.path,
                        ecosystem="all",
                    )
                except Exception:
                    return 0
            return report.summary.outdated

        async def vulnerabilities(repository: Repository) -> int:
            async with semaphore:
                try:
                    report = await self._security_service.get_report(
                        repository.id,
                        repository.path,
                        include_secrets=False,
                        min_severity="high",
                    )
                except Exception:
                    return 0
            return sum(
                len(ecosystem.vulnerabilities) for ecosystem in report.ecosystems
            )

        outdated_counts, cve_counts = await asyncio.gather(
            asyncio.gather(*(outdated(repository) for repository in repositories)),
            asyncio.gather(*(vulnerabilities(repository) for repository in repositories)),
        )
        stats["outdated_packages"] = sum(outdated_counts)
        stats["high_critical_cves"] = sum(cve_counts)
        return stats


__all__ = ["DashboardAdviceService", "DashboardAdviceUnavailableError"]
