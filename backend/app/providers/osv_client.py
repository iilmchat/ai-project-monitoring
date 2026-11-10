"""Read-only OSV.dev client and CVSS helpers (S28-001).

The client never raises on network errors: callers receive a result object with
``status="unavailable"`` so a single failed batch cannot break a report.
"""

from __future__ import annotations

import asyncio
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from app.schemas.security import SecuritySeverity

OSV_API = "https://api.osv.dev"
USER_AGENT = "IIRuchating/0.6"
MAX_BATCH_SIZE = 100

OsvEcosystem = Literal["PyPI", "npm", "NuGet"]
OsvStatus = Literal["ok", "rate_limited", "timeout", "unavailable"]

_CVSS_PREFIX = "CVSS:3."
_DATABASE_SEVERITY = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MODERATE": "medium",
    "MEDIUM": "medium",
    "LOW": "low",
}
_CVSS_METRIC = re.compile(r"([A-Z]{1,2}):([A-Z])")


@dataclass(frozen=True, slots=True)
class OsvQuery:
    """One package version to look up in OSV.dev."""

    package: str
    version: str
    ecosystem: OsvEcosystem


@dataclass(frozen=True, slots=True)
class OsvVulnerability:
    """Normalized OSV advisory."""

    osv_id: str
    summary: str
    severity: SecuritySeverity
    cvss_score: float | None = None
    aliases: tuple[str, ...] = ()
    fixed_version: str | None = None
    references: tuple[str, ...] = ()

    @property
    def cve_ids(self) -> tuple[str, ...]:
        return tuple(alias for alias in self.aliases if alias.startswith("CVE-"))


@dataclass(frozen=True, slots=True)
class OsvQueryResult:
    """Result of one OSV query within a batch."""

    vulns: tuple[OsvVulnerability, ...] = ()
    status: OsvStatus = "ok"
    error: str | None = None


class VulnerabilitySource(Protocol):
    """Minimal interface used by :class:`SecurityService`."""

    async def query_batch(
        self, queries: Sequence[OsvQuery]
    ) -> list[OsvQueryResult]:
        """Return one result per query, in the same order."""


class OsvClient:
    """Query OSV.dev ``/v1/querybatch`` without executing package managers."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        base_url: str = OSV_API,
        max_attempts: int = 3,
        batch_size: int = MAX_BATCH_SIZE,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = max(timeout_seconds, 0.1)
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max(max_attempts, 1)
        self._batch_size = max(1, min(batch_size, MAX_BATCH_SIZE))
        self._transport = transport

    async def query_batch(
        self, queries: Sequence[OsvQuery]
    ) -> list[OsvQueryResult]:
        results: list[OsvQueryResult] = []
        for start in range(0, len(queries), self._batch_size):
            chunk = list(queries[start : start + self._batch_size])
            results.extend(await self._query_chunk(chunk))
        return results

    async def _query_chunk(
        self, queries: list[OsvQuery]
    ) -> list[OsvQueryResult]:
        if not queries:
            return []
        payload = {
            "queries": [
                {
                    "package": {
                        "name": query.package,
                        "ecosystem": query.ecosystem,
                    },
                    "version": query.version,
                }
                for query in queries
            ]
        }
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        for attempt in range(self._max_attempts):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=headers,
                    transport=self._transport,
                ) as client:
                    response = await client.post("/v1/querybatch", json=payload)
            except httpx.TimeoutException:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return _failed(queries, status="timeout", error="timeout")
            except httpx.HTTPError:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return _failed(
                    queries, status="unavailable", error="osv_unavailable"
                )

            if response.status_code == 200:
                return self._parse_batch(response, queries)
            if response.status_code == 429:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return _failed(
                    queries, status="rate_limited", error="rate_limited"
                )
            if response.status_code in {500, 502, 503, 504}:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return _failed(
                    queries, status="unavailable", error="osv_unavailable"
                )
            return _failed(
                queries, status="unavailable", error="osv_unavailable"
            )

        return _failed(queries, status="unavailable", error="osv_unavailable")

    def _parse_batch(
        self,
        response: httpx.Response,
        queries: list[OsvQuery],
    ) -> list[OsvQueryResult]:
        try:
            payload = response.json()
        except ValueError:
            return _failed(
                queries, status="unavailable", error="osv_unavailable"
            )
        raw_results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(raw_results, list):
            return _failed(
                queries, status="unavailable", error="osv_unavailable"
            )

        parsed: list[OsvQueryResult] = []
        for index in range(len(queries)):
            raw = raw_results[index] if index < len(raw_results) else None
            parsed.append(_parse_query_result(raw))
        return parsed


def _failed(
    queries: list[OsvQuery],
    *,
    status: OsvStatus,
    error: str,
) -> list[OsvQueryResult]:
    return [
        OsvQueryResult(status=status, error=error) for _ in queries
    ]


def _parse_query_result(raw: object) -> OsvQueryResult:
    if not isinstance(raw, dict):
        return OsvQueryResult()
    raw_vulns = raw.get("vulns")
    if not isinstance(raw_vulns, list):
        return OsvQueryResult()

    by_id: dict[str, OsvVulnerability] = {}
    for item in raw_vulns:
        vulnerability = parse_vulnerability(item)
        if vulnerability is not None:
            by_id.setdefault(vulnerability.osv_id, vulnerability)
    return OsvQueryResult(vulns=tuple(by_id.values()))


def parse_vulnerability(raw: object) -> OsvVulnerability | None:
    """Normalize one OSV advisory, returning ``None`` for malformed entries."""
    if not isinstance(raw, dict):
        return None
    osv_id = raw.get("id")
    if not isinstance(osv_id, str) or not osv_id:
        return None

    summary_value = raw.get("summary")
    if not isinstance(summary_value, str):
        details = raw.get("details")
        summary_value = details if isinstance(details, str) else ""
    summary = summary_value

    score = _extract_cvss_score(raw.get("severity"))
    severity = severity_from_score(score)
    if severity == "unknown":
        severity = _database_severity(raw)

    aliases = _string_tuple(raw.get("aliases"))
    references = _reference_urls(raw.get("references"))
    fixed_version = _min_fixed_version(raw.get("affected"))

    return OsvVulnerability(
        osv_id=osv_id,
        summary=summary,
        severity=severity,
        cvss_score=score,
        aliases=aliases,
        fixed_version=fixed_version,
        references=references,
    )


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _reference_urls(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    urls: list[str] = []
    for item in value:
        if isinstance(item, dict):
            url = item.get("url")
            if isinstance(url, str) and url:
                urls.append(url)
    return tuple(urls)


def _extract_cvss_score(value: object) -> float | None:
    if not isinstance(value, list):
        return None
    scores: list[float] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        raw_score = item.get("score")
        if not isinstance(raw_score, str):
            continue
        parsed = parse_cvss_score(raw_score)
        if parsed is not None:
            scores.append(parsed)
    return max(scores) if scores else None


def _database_severity(raw: dict[str, object]) -> SecuritySeverity:
    for key in ("database_specific", "ecosystem_specific"):
        section = raw.get(key)
        if not isinstance(section, dict):
            continue
        value = section.get("severity")
        if isinstance(value, str):
            mapped = _DATABASE_SEVERITY.get(value.upper())
            if mapped is not None:
                return mapped  # type: ignore[return-value]
    return "unknown"


def _min_fixed_version(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    fixes: list[str] = []
    for affected in value:
        if not isinstance(affected, dict):
            continue
        ranges = affected.get("ranges")
        if not isinstance(ranges, list):
            continue
        for entry in ranges:
            if not isinstance(entry, dict):
                continue
            events = entry.get("events")
            if not isinstance(events, list):
                continue
            for event in events:
                if not isinstance(event, dict):
                    continue
                fixed = event.get("fixed")
                if isinstance(fixed, str) and fixed:
                    fixes.append(fixed)
    if not fixes:
        return None
    return min(fixes, key=version_key)


def version_key(value: str) -> tuple[int, ...]:
    """Release-only version key used for deterministic ordering."""
    match = re.match(r"^\s*v?(\d+(?:\.\d+)*)", value)
    if match is None:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("."))


def parse_cvss_score(value: str) -> float | None:
    """Return a CVSS v3 base score for a vector or numeric score."""
    text = value.strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        return numeric if 0.0 <= numeric <= 10.0 else None
    if not text.upper().startswith(_CVSS_PREFIX):
        return None
    metrics = dict(_CVSS_METRIC.findall(text.upper()))
    return _cvss_v3_base_score(metrics)


def _cvss_v3_base_score(metrics: dict[str, str]) -> float | None:
    av = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}.get(metrics.get("AV", ""))
    ac = {"L": 0.77, "H": 0.44}.get(metrics.get("AC", ""))
    ui = {"N": 0.85, "R": 0.62}.get(metrics.get("UI", ""))
    scope = metrics.get("S")
    if av is None or ac is None or ui is None or scope not in {"U", "C"}:
        return None

    pr_table = (
        {"N": 0.85, "L": 0.62, "H": 0.27}
        if scope == "U"
        else {"N": 0.85, "L": 0.68, "H": 0.5}
    )
    pr = pr_table.get(metrics.get("PR", ""))
    confidentiality = {"H": 0.56, "L": 0.22, "N": 0.0}.get(metrics.get("C", ""))
    integrity = {"H": 0.56, "L": 0.22, "N": 0.0}.get(metrics.get("I", ""))
    availability = {"H": 0.56, "L": 0.22, "N": 0.0}.get(metrics.get("A", ""))
    if pr is None or confidentiality is None or integrity is None or availability is None:
        return None

    iss = 1 - (1 - confidentiality) * (1 - integrity) * (1 - availability)
    impact = (
        6.42 * iss
        if scope == "U"
        else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    )
    if impact <= 0:
        return 0.0

    exploitability = 8.22 * av * ac * pr * ui
    if scope == "U":
        raw = min(impact + exploitability, 10.0)
    else:
        raw = min(1.08 * (impact + exploitability), 10.0)
    return math.ceil(round(raw, 6) * 10) / 10


def severity_from_score(score: float | None) -> SecuritySeverity:
    """Map a CVSS score to the canonical severity buckets from SPEC §3.16."""
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "unknown"


__all__ = [
    "MAX_BATCH_SIZE",
    "OSV_API",
    "OsvClient",
    "OsvEcosystem",
    "OsvQuery",
    "OsvQueryResult",
    "OsvStatus",
    "OsvVulnerability",
    "VulnerabilitySource",
    "parse_cvss_score",
    "parse_vulnerability",
    "severity_from_score",
    "version_key",
]
