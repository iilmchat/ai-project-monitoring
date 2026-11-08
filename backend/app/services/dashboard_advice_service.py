"""AI dashboard digest built from aggregated repository statistics (S38-001)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.models.entities import AICache, Repository
from app.schemas.ai import DashboardAdvice
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
    ) -> None:
        self._session_factory = session_factory
        self._dependency_service = dependency_service
        self._security_service = security_service
        self._llm = llm_service
        self._ttl = max(cache_ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)

    async def get_advice(self, language: str = "ru") -> DashboardAdvice:
        config = await self._llm.resolve()
        if not config.enabled or not self._llm.allows_remote(config):
            raise DashboardAdviceUnavailableError("llm_unavailable")

        cache_key = f"dashboard-advice:{language}:{config.model}"
        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is not None and _cache_is_fresh(row.checked_at, self._ttl):
                payload = row.payload if isinstance(row.payload, dict) else {}
                advice = payload.get("advice")
                if isinstance(advice, str) and advice:
                    return DashboardAdvice(
                        advice=advice,
                        cached=True,
                        model=row.model,
                        generated_at=utcnow(),
                        stats=_stats_from_payload(payload),
                    )

        stats = await self._collect_stats()
        advice = await self._llm.generate_dashboard_advice(
            stats,
            language=language,
        )
        if advice is None:
            raise DashboardAdviceUnavailableError("llm_unavailable")

        async with self._session_factory() as session:
            row = await session.get(AICache, cache_key)
            if row is None:
                row = AICache(
                    key=cache_key,
                    kind="dashboard_advice",
                    model=config.model,
                )
                session.add(row)
            row.payload = {"advice": advice, "stats": stats}
            row.checked_at = utcnow()
            await session.commit()

        return DashboardAdvice(
            advice=advice,
            cached=False,
            model=config.model,
            generated_at=utcnow(),
            stats=stats,
        )

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


def _stats_from_payload(payload: dict[str, object]) -> dict[str, int]:
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        return {}
    return {
        key: int(value)
        for key, value in stats.items()
        if isinstance(key, str) and isinstance(value, int | float)
    }


def _cache_is_fresh(checked_at: datetime, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0:
        return False
    value = checked_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return 0 <= (utcnow() - value).total_seconds() < ttl_seconds


__all__ = ["DashboardAdviceService", "DashboardAdviceUnavailableError"]
