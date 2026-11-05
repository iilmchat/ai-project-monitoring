"""Python/Node dependency checks with a persistent TTL cache (S25–S26)."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.models.entities import DependencyCache
from app.providers.package_versions import PackageVersionResult
from app.schemas.dependency import (
    DependencyEcosystemReport,
    DependencyPackage,
    DependencyPackageStatus,
    DependencyReport,
    DependencySeverity,
    DependencySource,
    DependencySummary,
)
from app.services.dependency_parser import (
    ParsedRequirement,
    parse_requirements,
)
from app.services.node_parser import parse_package_json

IGNORED_KINDS = frozenset({"vcs", "path", "workspace"})
LookupSource = Literal["registry", "cache", "stale_cache", "none"]
RegistryPrefix = Literal["pypi", "npm"]
Ecosystem = Literal["python", "node"]


class LatestVersionRegistry(Protocol):
    """Minimal registry interface used by :class:`DependencyService`."""

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        """Return the latest known version for ``package``."""


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    latest: str | None
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class _Lookup:
    latest: str | None
    source: LookupSource
    error: str | None = None


class DependencyService:
    """Check declared dependencies without executing package managers."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        pypi_registry: LatestVersionRegistry,
        npm_registry: LatestVersionRegistry | None = None,
        *,
        cache_ttl_seconds: int = 86400,
        concurrency: int = 4,
        max_include_depth: int = 3,
    ) -> None:
        self._session_factory = session_factory
        self._pypi_registry = pypi_registry
        self._npm_registry = npm_registry
        self._ttl = max(cache_ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)
        self._max_include_depth = max(max_include_depth, 0)
        self._locks: dict[str, asyncio.Lock] = {}
        self._cache_write_lock = asyncio.Lock()

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        ecosystem: str | None = None,
        refresh: bool = False,
    ) -> DependencyReport:
        """Build a dependency report for one repository.

        ``ecosystem`` accepts ``python``, ``node``, ``all`` or ``None``.
        ``None`` and ``all`` both produce the combined report.
        """
        if ecosystem not in (None, "python", "node", "all"):
            raise ValueError(f"unsupported ecosystem: {ecosystem}")

        requested: list[Ecosystem] = (
            ["python", "node"]
            if ecosystem in (None, "all")
            else [ecosystem]  # type: ignore[list-item]
        )
        reports: list[DependencyEcosystemReport] = []
        for name in requested:
            if name == "python":
                reports.append(
                    await self._python_report(repo_path, refresh=refresh)
                )
            else:
                reports.append(
                    await self._node_report(repo_path, refresh=refresh)
                )

        summary = DependencySummary(
            total=sum(item.total for item in reports),
            outdated=sum(item.outdated for item in reports),
            up_to_date=sum(item.up_to_date for item in reports),
            unknown=sum(item.unknown for item in reports),
            ignored=sum(item.ignored for item in reports),
        )
        return DependencyReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            ecosystems=reports,
            summary=summary,
        )

    async def _python_report(
        self,
        repo_path: str,
        *,
        refresh: bool,
    ) -> DependencyEcosystemReport:
        parsed = parse_requirements(
            Path(repo_path),
            max_include_depth=self._max_include_depth,
        )
        if not parsed.manifest_found:
            return _empty_report(
                ecosystem="python",
                manifest="requirements.txt",
                status="no_manifest",
            )
        if parsed.error is not None:
            return DependencyEcosystemReport(
                ecosystem="python",
                manifest="requirements.txt",
                status="parse_error",
                source="none",
                error=parsed.error,
            )
        return await self._check_requirements(
            parsed.packages,
            ecosystem="python",
            manifest="requirements.txt",
            registry_prefix="pypi",
            registry=self._pypi_registry,
            refresh=refresh,
        )

    async def _node_report(
        self,
        repo_path: str,
        *,
        refresh: bool,
    ) -> DependencyEcosystemReport:
        parsed = parse_package_json(Path(repo_path))
        if not parsed.manifest_found:
            return _empty_report(
                ecosystem="node",
                manifest="package.json",
                status="no_manifest",
            )
        if parsed.error is not None:
            return DependencyEcosystemReport(
                ecosystem="node",
                manifest="package.json",
                status="parse_error",
                source="none",
                error=parsed.error,
            )
        if self._npm_registry is None:
            return DependencyEcosystemReport(
                ecosystem="node",
                manifest="package.json",
                status="unavailable",
                source="none",
                error="npm_client_not_configured",
            )
        return await self._check_requirements(
            parsed.packages,
            ecosystem="node",
            manifest="package.json",
            registry_prefix="npm",
            registry=self._npm_registry,
            refresh=refresh,
        )

    async def _check_requirements(
        self,
        requirements: list[ParsedRequirement],
        *,
        ecosystem: Ecosystem,
        manifest: str,
        registry_prefix: RegistryPrefix,
        registry: LatestVersionRegistry,
        refresh: bool,
    ) -> DependencyEcosystemReport:
        semaphore = asyncio.Semaphore(self._concurrency)
        tasks: list[asyncio.Task[_Lookup]] = []
        for requirement in requirements:
            if requirement.kind in IGNORED_KINDS:
                tasks.append(asyncio.create_task(_ignored_lookup()))
            else:
                tasks.append(
                    asyncio.create_task(
                        self._lookup(
                            requirement.name,
                            registry_prefix=registry_prefix,
                            registry=registry,
                            refresh=refresh,
                            semaphore=semaphore,
                        )
                    )
                )
        lookups = await asyncio.gather(*tasks)

        packages = [
            _package_report(requirement, lookup)
            for requirement, lookup in zip(requirements, lookups, strict=True)
        ]
        checked = [
            lookup
            for requirement, lookup in zip(requirements, lookups, strict=True)
            if requirement.kind not in IGNORED_KINDS
        ]
        counts = _count_statuses(packages)
        source = _aggregate_source(checked)
        error = next((item.error for item in checked if item.error), None)
        status = (
            "unavailable"
            if checked and all(item.error is not None and item.latest is None for item in checked)
            else "ok"
        )
        return DependencyEcosystemReport(
            ecosystem=ecosystem,
            manifest=manifest,
            status=status,
            source=source,
            total=len(packages),
            outdated=counts["outdated"],
            up_to_date=counts["current"],
            unknown=counts["unknown"],
            ignored=counts["ignored"],
            packages=packages,
            error=error,
        )

    async def _lookup(
        self,
        package: str,
        *,
        registry_prefix: RegistryPrefix,
        registry: LatestVersionRegistry,
        refresh: bool,
        semaphore: asyncio.Semaphore,
    ) -> _Lookup:
        key = f"{registry_prefix}:{package}"
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            cached = await self._read_cache(key)
            if cached is not None and not refresh and self._is_fresh(cached.checked_at):
                return _Lookup(latest=cached.latest, source="cache")

            try:
                async with semaphore:
                    result = await registry.get_latest_version(package)
            except Exception:
                result = PackageVersionResult(
                    latest=None,
                    status="unavailable",
                    error="registry_unavailable",
                )

            if result.status in {"ok", "not_found"}:
                await self._write_cache(key, registry_prefix, package, result)
                return _Lookup(latest=result.latest, source="registry")
            if cached is not None:
                return _Lookup(
                    latest=cached.latest,
                    source="stale_cache",
                    error=result.error or result.status,
                )
            return _Lookup(
                latest=None,
                source="none",
                error=result.error or result.status,
            )

    async def _read_cache(self, key: str) -> _CacheEntry | None:
        async with self._session_factory() as session:
            row = await session.get(DependencyCache, key)
            if row is None:
                return None
            return _CacheEntry(latest=row.latest_version, checked_at=row.checked_at)

    async def _write_cache(
        self,
        key: str,
        registry_prefix: RegistryPrefix,
        package: str,
        result: PackageVersionResult,
    ) -> None:
        # SQLite does not like concurrent writers; serialise short upserts.
        async with self._cache_write_lock, self._session_factory() as session:
            row = await session.get(DependencyCache, key)
            if row is None:
                row = DependencyCache(
                    key=key,
                    ecosystem=registry_prefix,
                    package=package,
                )
                session.add(row)
            row.latest_version = result.latest
            row.etag = result.etag
            row.payload = {"status": result.status}
            row.checked_at = utcnow()
            await session.commit()

    def _is_fresh(self, checked_at: datetime) -> bool:
        if self._ttl <= 0:
            return False
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        age = (utcnow() - checked_at).total_seconds()
        return 0 <= age < self._ttl


async def _ignored_lookup() -> _Lookup:
    return _Lookup(latest=None, source="none")


def _empty_report(
    *,
    ecosystem: Ecosystem,
    manifest: str,
    status: Literal["no_manifest", "parse_error"],
) -> DependencyEcosystemReport:
    return DependencyEcosystemReport(
        ecosystem=ecosystem,
        manifest=manifest,
        status=status,
        source="none",
    )


def _package_report(
    requirement: ParsedRequirement,
    lookup: _Lookup,
) -> DependencyPackage:
    if requirement.kind in IGNORED_KINDS:
        return DependencyPackage(
            name=requirement.name,
            declared=requirement.declared,
            current=requirement.current,
            latest=None,
            status="ignored",
            kind=requirement.kind,
            manifest_line=requirement.manifest_line,
            manifest_section=requirement.manifest_section,
        )

    status, severity = _classify(requirement.current, lookup.latest)
    return DependencyPackage(
        name=requirement.name,
        declared=requirement.declared,
        current=requirement.current,
        latest=lookup.latest,
        status=status,
        kind=requirement.kind,
        severity=severity,
        manifest_line=requirement.manifest_line,
        manifest_section=requirement.manifest_section,
    )


def _aggregate_source(checked: list[_Lookup]) -> DependencySource:
    sources = {item.source for item in checked if item.source != "none"}
    if not sources:
        return "none"
    if "stale_cache" in sources:
        return "stale_cache"
    if sources == {"registry"}:
        return "registry"
    if sources == {"cache"}:
        return "cache"
    return "mixed"


def _count_statuses(
    packages: list[DependencyPackage],
) -> dict[str, int]:
    counts = {"outdated": 0, "current": 0, "unknown": 0, "ignored": 0}
    for package in packages:
        counts[package.status] += 1
    return counts


def _classify(
    current: str | None,
    latest: str | None,
) -> tuple[DependencyPackageStatus, DependencySeverity | None]:
    if current is None or latest is None:
        return "unknown", None
    current_version = _parse_version(current)
    latest_version = _parse_version(latest)
    if current_version is None or latest_version is None:
        return "unknown", None
    if latest_version <= current_version:
        return "current", None
    return "outdated", _severity(current_version, latest_version)


def _parse_version(value: str) -> tuple[int, ...] | None:
    match = re.match(r"^\s*v?(?:\d+!)?(\d+(?:\.\d+)*)", value)
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _severity(
    current: tuple[int, ...],
    latest: tuple[int, ...],
) -> DependencySeverity:
    length = max(len(current), len(latest))
    for index in range(length):
        current_part = current[index] if index < len(current) else 0
        latest_part = latest[index] if index < len(latest) else 0
        if current_part != latest_part:
            if index == 0:
                return "major"
            if index == 1:
                return "minor"
            return "patch"
    return "patch"


__all__ = ["DependencyService", "LatestVersionRegistry"]
