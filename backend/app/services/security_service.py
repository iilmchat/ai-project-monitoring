"""CVE and secret scanning service (S28-001…S28-004, .NET — S57-002)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.base import utcnow
from app.models.entities import SecurityCache
from app.providers.osv_client import (
    OsvEcosystem,
    OsvQuery,
    OsvQueryResult,
    OsvVulnerability,
    VulnerabilitySource,
)
from app.schemas.security import (
    SecretScanReport,
    SecurityEcosystemReport,
    SecurityReport,
    SecuritySeverity,
    SecuritySummary,
    SecurityUnknownPackage,
    SecurityVersionSource,
    SecurityVulnerability,
)
from app.services.dependency_parser import ParsedRequirement
from app.services.manifest_discovery import (
    discover_manifests,
    parse_dotnet_manifests,
    parse_node_manifests,
    parse_python_manifests,
)
from app.services.secret_scanner import scan_secrets

MinSeverity = Literal["critical", "high", "medium", "low", "all"]
Ecosystem = Literal["python", "node", "dotnet"]

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
_IGNORED_KINDS = frozenset({"vcs", "path", "workspace"})


@dataclass(frozen=True, slots=True)
class _Candidate:
    name: str
    version: str
    source: SecurityVersionSource


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    vulns: tuple[OsvVulnerability, ...]
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class _Lookup:
    vulns: tuple[OsvVulnerability, ...]
    checked: bool
    error: str | None = None


class SecurityService:
    """Check declared dependencies against OSV.dev and scan for secrets."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        osv_client: VulnerabilitySource,
        *,
        cache_ttl_seconds: int = 21600,
        concurrency: int = 4,
        max_include_depth: int = 3,
        manifest_max_depth: int = 3,
        secret_scan_enabled: bool = True,
        secret_scan_max_files: int = 5000,
        secret_scan_max_file_bytes: int = 1_048_576,
        secret_scan_ttl_seconds: int = 300,
    ) -> None:
        self._session_factory = session_factory
        self._osv_client = osv_client
        self._ttl = max(cache_ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)
        self._max_include_depth = max(max_include_depth, 0)
        self._manifest_max_depth = max(manifest_max_depth, 0)
        self._secret_scan_enabled = secret_scan_enabled
        self._secret_max_files = max(secret_scan_max_files, 1)
        self._secret_max_bytes = max(secret_scan_max_file_bytes, 1)
        self._secret_ttl = max(secret_scan_ttl_seconds, 0)
        self._secret_cache: dict[str, tuple[float, SecretScanReport]] = {}
        self._write_lock = asyncio.Lock()

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        refresh: bool = False,
        include_secrets: bool = True,
        min_severity: MinSeverity = "high",
    ) -> SecurityReport:
        """Build a security report for one repository."""
        if min_severity not in {"critical", "high", "medium", "low", "all"}:
            raise ValueError(f"unsupported min_severity: {min_severity}")

        ecosystems = [
            await self._python_report(repo_path, refresh=refresh),
            await self._node_report(repo_path, refresh=refresh),
            await self._dotnet_report(repo_path, refresh=refresh),
        ]
        secrets = await self._secrets_report(
            repo_path,
            refresh=refresh,
            include_secrets=include_secrets,
        )

        visible = [
            vulnerability
            for ecosystem in ecosystems
            for vulnerability in ecosystem.vulnerabilities
        ]
        if min_severity != "all":
            threshold = _SEVERITY_RANK[min_severity]
            visible = [
                item
                for item in visible
                if _SEVERITY_RANK[item.severity] <= threshold
            ]

        summary = SecuritySummary(
            total_packages=sum(item.total_packages for item in ecosystems),
            packages_checked=sum(item.packages_checked for item in ecosystems),
            vulnerable=len(
                {
                    (ecosystem.ecosystem, vulnerability.package)
                    for ecosystem in ecosystems
                    for vulnerability in ecosystem.vulnerabilities
                }
            ),
            critical=sum(
                1 for item in ecosystems for _ in _by_severity(item, "critical")
            ),
            high=sum(1 for item in ecosystems for _ in _by_severity(item, "high")),
            medium=sum(
                1 for item in ecosystems for _ in _by_severity(item, "medium")
            ),
            low=sum(1 for item in ecosystems for _ in _by_severity(item, "low")),
            unknown=sum(len(item.unknown_packages) for item in ecosystems),
            secrets_found=len(secrets.findings),
        )

        manifest_reports = [
            item for item in ecosystems if item.status != "no_manifest"
        ]
        status: Literal["ok", "unavailable"] = (
            "unavailable"
            if manifest_reports
            and all(item.status == "unavailable" for item in manifest_reports)
            else "ok"
        )
        if min_severity != "all":
            visible_ids = {(item.osv_id, item.package) for item in visible}
            for ecosystem in ecosystems:
                ecosystem.vulnerabilities = [
                    item
                    for item in ecosystem.vulnerabilities
                    if (item.osv_id, item.package) in visible_ids
                ]

        error = next(
            (item.error for item in ecosystems if item.error is not None),
            secrets.error,
        )
        return SecurityReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            status=status,
            summary=summary,
            ecosystems=ecosystems,
            secrets=secrets,
            error=error,
        )

    async def _python_report(
        self, repo_path: str, *, refresh: bool
    ) -> SecurityEcosystemReport:
        discovered = discover_manifests(
            repo_path,
            max_depth=self._manifest_max_depth,
        )
        parsed = parse_python_manifests(
            discovered,
            max_include_depth=self._max_include_depth,
        )
        if not parsed.manifest_found:
            return _empty("python", "requirements.txt", "no_manifest")
        if not parsed.packages and parsed.errors:
            return _empty(
                "python",
                parsed.manifest_label or "requirements.txt",
                "parse_error",
                error="; ".join(parsed.errors),
                manifests=parsed.manifests,
            )
        report = await self._check(
            parsed.packages,
            ecosystem="python",
            manifest=parsed.manifest_label or "requirements.txt",
            manifests=parsed.manifests,
            osv_ecosystem="PyPI",
            cache_prefix="pypi",
            refresh=refresh,
        )
        if parsed.errors:
            report.error = "; ".join(parsed.errors)
        return report

    async def _node_report(
        self, repo_path: str, *, refresh: bool
    ) -> SecurityEcosystemReport:
        discovered = discover_manifests(
            repo_path,
            max_depth=self._manifest_max_depth,
        )
        parsed = parse_node_manifests(discovered)
        if not parsed.manifest_found:
            return _empty("node", "package.json", "no_manifest")
        if not parsed.packages and parsed.errors:
            return _empty(
                "node",
                parsed.manifest_label or "package.json",
                "parse_error",
                error="; ".join(parsed.errors),
                manifests=parsed.manifests,
            )
        report = await self._check(
            parsed.packages,
            ecosystem="node",
            manifest=parsed.manifest_label or "package.json",
            manifests=parsed.manifests,
            osv_ecosystem="npm",
            cache_prefix="npm",
            refresh=refresh,
        )
        if parsed.errors:
            report.error = "; ".join(parsed.errors)
        return report

    async def _dotnet_report(
        self, repo_path: str, *, refresh: bool
    ) -> SecurityEcosystemReport:
        discovered = discover_manifests(
            repo_path,
            max_depth=self._manifest_max_depth,
        )
        parsed = parse_dotnet_manifests(discovered)
        if not parsed.manifest_found:
            return _empty("dotnet", "*.csproj", "no_manifest")
        if not parsed.packages and parsed.errors:
            return _empty(
                "dotnet",
                parsed.manifest_label or "*.csproj",
                "parse_error",
                error="; ".join(parsed.errors),
                manifests=parsed.manifests,
            )
        report = await self._check(
            parsed.packages,
            ecosystem="dotnet",
            manifest=parsed.manifest_label or "*.csproj",
            manifests=parsed.manifests,
            osv_ecosystem="NuGet",
            cache_prefix="nuget",
            refresh=refresh,
        )
        if parsed.errors:
            report.error = "; ".join(parsed.errors)
        return report

    async def _check(
        self,
        requirements: list[ParsedRequirement],
        *,
        ecosystem: Ecosystem,
        manifest: str,
        manifests: list[str],
        osv_ecosystem: OsvEcosystem,
        cache_prefix: str,
        refresh: bool,
    ) -> SecurityEcosystemReport:
        candidates: dict[tuple[str, str], _Candidate] = {}
        unknown: list[SecurityUnknownPackage] = []
        unknown_names: set[str] = set()

        for requirement in requirements:
            if requirement.kind in _IGNORED_KINDS:
                continue
            if requirement.current is None:
                if requirement.name not in unknown_names:
                    unknown_names.add(requirement.name)
                    unknown.append(
                        SecurityUnknownPackage(
                            name=requirement.name,
                            reason=(
                                "unresolved_version"
                                if ecosystem == "dotnet"
                                else "unresolved_range"
                            ),
                        )
                    )
                continue
            key = (requirement.name, requirement.current)
            source: SecurityVersionSource = (
                "exact" if requirement.kind == "exact" else "lower_bound"
            )
            existing = candidates.get(key)
            if existing is None or source == "exact":
                candidates[key] = _Candidate(
                    name=requirement.name,
                    version=requirement.current,
                    source=source,
                )

        ordered = list(candidates.values())
        cache_keys = {
            _cache_key(cache_prefix, item): item for item in ordered
        }
        cached = await self._read_cache_many(list(cache_keys))
        lookups: dict[str, _Lookup] = {}
        pending: list[tuple[str, _Candidate]] = []

        for cache_key, candidate in cache_keys.items():
            entry = cached.get(cache_key)
            if (
                entry is not None
                and not refresh
                and self._is_fresh(entry.checked_at)
            ):
                lookups[cache_key] = _Lookup(vulns=entry.vulns, checked=True)
            else:
                pending.append((cache_key, candidate))

        to_query = [
            OsvQuery(
                package=candidate.name,
                version=candidate.version,
                ecosystem=osv_ecosystem,
            )
            for _, candidate in pending
        ]
        query_results: list[OsvQueryResult] = []
        if to_query:
            try:
                query_results = await self._osv_client.query_batch(to_query)
            except Exception:
                query_results = [
                    OsvQueryResult(
                        status="unavailable", error="osv_unavailable"
                    )
                    for _ in to_query
                ]

        to_cache: list[tuple[str, _Candidate, tuple[OsvVulnerability, ...]]] = []
        for index, (cache_key, candidate) in enumerate(pending):
            result = (
                query_results[index]
                if index < len(query_results)
                else OsvQueryResult(
                    status="unavailable", error="osv_unavailable"
                )
            )
            entry = cached.get(cache_key)
            if result.status == "ok":
                lookups[cache_key] = _Lookup(vulns=result.vulns, checked=True)
                to_cache.append((cache_key, candidate, result.vulns))
            elif entry is not None:
                lookups[cache_key] = _Lookup(
                    vulns=entry.vulns,
                    checked=True,
                    error=result.error or result.status,
                )
            else:
                lookups[cache_key] = _Lookup(
                    vulns=(),
                    checked=False,
                    error=result.error or result.status,
                )

        if to_cache:
            await self._write_cache_many(cache_prefix, to_cache)

        for cache_key, candidate in pending:
            lookup = lookups.get(cache_key)
            if (
                lookup is not None
                and not lookup.checked
                and candidate.name not in unknown_names
            ):
                unknown_names.add(candidate.name)
                unknown.append(
                    SecurityUnknownPackage(
                        name=candidate.name,
                        reason="osv_unavailable",
                    )
                )

        vulnerabilities: list[SecurityVulnerability] = []
        seen: set[tuple[str, str]] = set()
        for cache_key, candidate in cache_keys.items():
            lookup = lookups.get(cache_key)
            if lookup is None:
                continue
            for vulnerability in lookup.vulns:
                dedupe_key = (candidate.name, vulnerability.osv_id)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                vulnerabilities.append(
                    SecurityVulnerability(
                        package=candidate.name,
                        version=candidate.version,
                        version_source=candidate.source,
                        osv_id=vulnerability.osv_id,
                        cve_ids=list(vulnerability.cve_ids),
                        severity=vulnerability.severity,
                        cvss_score=vulnerability.cvss_score,
                        summary=vulnerability.summary or None,
                        fixed_version=vulnerability.fixed_version,
                        references=list(vulnerability.references),
                    )
                )
        vulnerabilities.sort(key=_vulnerability_sort_key)

        checked_names = {
            candidate.name
            for cache_key, candidate in cache_keys.items()
            if (lookup := lookups.get(cache_key)) is not None and lookup.checked
        }
        declared_names = {candidate.name for candidate in ordered} | {
            item.name for item in unknown
        }
        status: Literal["ok", "unavailable"] = (
            "ok"
            if not ordered or checked_names
            else "unavailable"
        )
        error = next(
            (lookup.error for lookup in lookups.values() if lookup.error), None
        )
        return SecurityEcosystemReport(
            ecosystem=ecosystem,
            manifest=manifest,
            manifests=manifests,
            status=status,
            total_packages=len(declared_names),
            packages_checked=len(checked_names),
            vulnerabilities=vulnerabilities,
            unknown_packages=unknown,
            error=error,
        )

    async def _secrets_report(
        self,
        repo_path: str,
        *,
        refresh: bool,
        include_secrets: bool,
    ) -> SecretScanReport:
        if not include_secrets or not self._secret_scan_enabled:
            return SecretScanReport(status="skipped", error=None)

        key = str(Path(repo_path).resolve())
        if not refresh and self._secret_ttl > 0:
            cached = self._secret_cache.get(key)
            if cached is not None:
                age = time.monotonic() - cached[0]
                if 0 <= age < self._secret_ttl:
                    return cached[1].model_copy(deep=True)

        report = await asyncio.to_thread(
            scan_secrets,
            repo_path,
            max_files=self._secret_max_files,
            max_file_bytes=self._secret_max_bytes,
        )
        self._secret_cache[key] = (time.monotonic(), report)
        return report.model_copy(deep=True)

    async def _read_cache_many(
        self, keys: list[str]
    ) -> dict[str, _CacheEntry]:
        entries: dict[str, _CacheEntry] = {}
        if not keys:
            return entries
        async with self._session_factory() as session:
            for key in keys:
                row = await session.get(SecurityCache, key)
                if row is None:
                    continue
                entries[key] = _CacheEntry(
                    vulns=_deserialize(row.payload),
                    checked_at=row.checked_at,
                )
        return entries

    async def _write_cache_many(
        self,
        cache_prefix: str,
        entries: list[tuple[str, _Candidate, tuple[OsvVulnerability, ...]]],
    ) -> None:
        # SQLite dislikes concurrent writers; serialise short upserts.
        async with self._write_lock, self._session_factory() as session:
            for key, candidate, vulns in entries:
                row = await session.get(SecurityCache, key)
                if row is None:
                    row = SecurityCache(
                        key=key,
                        ecosystem=cache_prefix,
                        package=candidate.name,
                        version=candidate.version,
                    )
                    session.add(row)
                row.payload = _serialize(vulns)
                row.checked_at = utcnow()
            await session.commit()

    def _is_fresh(self, checked_at: datetime) -> bool:
        if self._ttl <= 0:
            return False
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)
        age = (utcnow() - checked_at).total_seconds()
        return 0 <= age < self._ttl


def _empty(
    ecosystem: Ecosystem,
    manifest: str,
    status: Literal["no_manifest", "parse_error"],
    *,
    error: str | None = None,
    manifests: list[str] | None = None,
) -> SecurityEcosystemReport:
    return SecurityEcosystemReport(
        ecosystem=ecosystem,
        manifest=manifest,
        manifests=manifests or [],
        status=status,
        error=error,
    )


def _cache_key(prefix: str, candidate: _Candidate) -> str:
    name = candidate.name.lower() if prefix == "nuget" else candidate.name
    return f"osv:{prefix}:{name}:{candidate.version}"


def _serialize(vulns: Sequence[OsvVulnerability]) -> dict[str, Any]:
    return {
        "vulns": [
            {
                "osv_id": item.osv_id,
                "summary": item.summary,
                "severity": item.severity,
                "cvss_score": item.cvss_score,
                "aliases": list(item.aliases),
                "fixed_version": item.fixed_version,
                "references": list(item.references),
            }
            for item in vulns
        ]
    }


def _deserialize(payload: object) -> tuple[OsvVulnerability, ...]:
    if not isinstance(payload, dict):
        return ()
    raw = payload.get("vulns")
    if not isinstance(raw, list):
        return ()
    parsed: list[OsvVulnerability] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        osv_id = item.get("osv_id")
        if not isinstance(osv_id, str) or not osv_id:
            continue
        severity = item.get("severity")
        if severity not in _SEVERITY_RANK:
            severity = "unknown"
        score = item.get("cvss_score")
        summary_raw = item.get("summary")
        summary_text = summary_raw if isinstance(summary_raw, str) else ""
        parsed.append(
            OsvVulnerability(
                osv_id=osv_id,
                summary=summary_text,
                severity=severity,  # type: ignore[arg-type]
                cvss_score=float(score) if isinstance(score, int | float) else None,
                aliases=tuple(
                    alias
                    for alias in item.get("aliases", [])
                    if isinstance(alias, str)
                )
                if isinstance(item.get("aliases"), list)
                else (),
                fixed_version=item.get("fixed_version")
                if isinstance(item.get("fixed_version"), str)
                else None,
                references=tuple(
                    url
                    for url in item.get("references", [])
                    if isinstance(url, str)
                )
                if isinstance(item.get("references"), list)
                else (),
            )
        )
    return tuple(parsed)


def _by_severity(
    report: SecurityEcosystemReport, severity: SecuritySeverity
) -> list[SecurityVulnerability]:
    return [
        item for item in report.vulnerabilities if item.severity == severity
    ]


def _vulnerability_sort_key(item: SecurityVulnerability) -> tuple[int, str, str]:
    return (_SEVERITY_RANK[item.severity], item.package, item.osv_id)


__all__ = ["MinSeverity", "SecurityService"]
