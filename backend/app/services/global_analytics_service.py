"""Global dependency aggregation across tracked repositories (S33-001)."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.models.entities import Repository
from app.schemas.dependency import DependencyReport
from app.schemas.global_analytics import (
    GlobalDependencyPackage,
    GlobalDependencyReport,
    GlobalDependencySummary,
    VersionDistribution,
)
from app.services.dependency_service import DependencyService

_VERSION_RE = re.compile(r"^\s*v?(?:\d+!)?(\d+(?:\.\d+)*)")


@dataclass(slots=True)
class _Aggregate:
    latest: str | None = None
    versions: dict[str, set[str]] = field(default_factory=dict)


class GlobalAnalyticsService:
    """Aggregate declared package versions over all tracked repositories."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dependency_service: DependencyService,
        *,
        cache_ttl_seconds: int = 3600,
        limit: int = 50,
        concurrency: int = 4,
    ) -> None:
        self._session_factory = session_factory
        self._dependency_service = dependency_service
        self._ttl = max(cache_ttl_seconds, 0)
        self._limit = max(min(limit, 200), 1)
        self._concurrency = max(concurrency, 1)
        self._cache: tuple[float, GlobalDependencyReport] | None = None

    async def get_global_dependencies(
        self, *, refresh: bool = False
    ) -> GlobalDependencyReport:
        """Return the cached global report, rebuilding it when stale."""
        if not refresh and self._ttl > 0 and self._cache is not None:
            cached_at, cached = self._cache
            if 0 <= time.monotonic() - cached_at < self._ttl:
                return cached.model_copy(deep=True)

        report = await self._build(refresh=refresh)
        self._cache = (time.monotonic(), report)
        return report.model_copy(deep=True)

    async def _build(self, *, refresh: bool) -> GlobalDependencyReport:
        async with self._session_factory() as session:
            repositories = (
                await session.scalars(
                    select(Repository)
                    .where(Repository.tracked.is_(True))
                    .order_by(Repository.path)
                )
            ).all()
            rows = [
                (repository.id, repository.path, repository.alias)
                for repository in repositories
            ]

        semaphore = asyncio.Semaphore(self._concurrency)

        async def collect(
            repository_id: int, path: str, alias: str | None
        ) -> tuple[str, DependencyReport | None]:
            label = alias or Path(path).name or path
            async with semaphore:
                try:
                    report = await self._dependency_service.get_report(
                        repository_id,
                        path,
                        ecosystem="all",
                        refresh=refresh,
                    )
                except Exception:
                    return label, None
            return label, report

        results = await asyncio.gather(
            *(collect(repository_id, path, alias) for repository_id, path, alias in rows)
        )

        aggregates: dict[str, dict[str, _Aggregate]] = {
            "python": {},
            "node": {},
        }
        errors = 0
        for label, report in results:
            if report is None:
                errors += 1
                continue
            for ecosystem in report.ecosystems:
                bucket = aggregates.get(ecosystem.ecosystem)
                if bucket is None:
                    continue
                for package in ecosystem.packages:
                    if package.status == "ignored" or package.current is None:
                        continue
                    aggregate = bucket.setdefault(package.name, _Aggregate())
                    aggregate.versions.setdefault(package.current, set()).add(label)
                    if package.latest is not None and (
                        aggregate.latest is None
                        or _version_key(package.latest) > _version_key(aggregate.latest)
                    ):
                        aggregate.latest = package.latest

        ecosystems = {
            "python": self._packages(aggregates["python"]),
            "node": self._packages(aggregates["node"]),
        }
        total_packages = sum(len(bucket) for bucket in aggregates.values())
        unification_candidates = sum(
            1
            for bucket in aggregates.values()
            for aggregate in bucket.values()
            if len(aggregate.versions) > 1
        )
        return GlobalDependencyReport(
            checked_at=utcnow(),
            ecosystems=ecosystems,
            summary=GlobalDependencySummary(
                repositories=len(rows),
                packages=total_packages,
                unification_candidates=unification_candidates,
            ),
            error="partial_errors" if errors else None,
        )

    def _packages(
        self, bucket: dict[str, _Aggregate]
    ) -> list[GlobalDependencyPackage]:
        packages: list[GlobalDependencyPackage] = []
        for name, aggregate in bucket.items():
            distribution = [
                VersionDistribution(
                    version=version,
                    projects=sorted(projects),
                )
                for version, projects in sorted(
                    aggregate.versions.items(),
                    key=lambda item: (_version_key(item[0]), item[0]),
                )
            ]
            projects = {
                project
                for distribution_item in distribution
                for project in distribution_item.projects
            }
            packages.append(
                GlobalDependencyPackage(
                    name=name,
                    latest_version=aggregate.latest,
                    distribution=distribution,
                    versions_count=len(aggregate.versions),
                    projects_count=len(projects),
                    unification_needed=len(aggregate.versions) > 1,
                )
            )
        packages.sort(key=lambda package: (-package.projects_count, package.name))
        return packages[: self._limit]


def _version_key(value: str) -> tuple[int, ...]:
    match = _VERSION_RE.match(value)
    if match is None:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("."))


__all__ = ["GlobalAnalyticsService"]
