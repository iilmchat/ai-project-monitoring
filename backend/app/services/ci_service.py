"""CI status aggregation with a small TTL cache (S19-001)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from app.config import Settings
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient


def aggregate_ci(results: list[dict[str, object]]) -> str:
    statuses = {str(item.get("status")) for item in results}
    conclusions = {item.get("conclusion") for item in results}
    if "failure" in conclusions or "timed_out" in conclusions:
        return "failure"
    if "cancelled" in conclusions:
        return "cancelled"
    if statuses & {"queued", "in_progress", "pending"}:
        return "pending"
    if "success" in conclusions and statuses <= {
        "completed",
        "success",
        "none",
        "not_supported",
        "not_configured",
    }:
        return "success"
    if statuses <= {"none", "not_supported", "not_configured"}:
        return "none"
    return "unknown"


@dataclass(frozen=True, slots=True)
class CISummary:
    github: str
    gitflic: str
    aggregate: str


def _not_configured(provider: str) -> dict[str, object]:
    return {
        "provider": provider,
        "status": "not_configured",
        "conclusion": None,
        "url": None,
    }


class CIService:
    """Fetch CI statuses for dashboard rows, cached per repository+branch."""

    def __init__(
        self,
        github: GitHubClient,
        gitflic: GitFlicClient,
        settings: Settings,
        *,
        ttl_seconds: int = 60,
        concurrency: int = 5,
    ) -> None:
        self._github = github
        self._gitflic = gitflic
        self._settings = settings
        self._ttl = max(ttl_seconds, 0)
        self._concurrency = max(concurrency, 1)
        self._cache: dict[tuple[int, str], tuple[float, CISummary]] = {}

    async def get_many(
        self,
        rows: list[tuple[int, str, str | None, str | None]],
    ) -> dict[int, CISummary]:
        semaphore = asyncio.Semaphore(self._concurrency)

        async def worker(
            row: tuple[int, str, str | None, str | None]
        ) -> tuple[int, CISummary]:
            repository_id, branch, github_name, gitflic_name = row
            async with semaphore:
                summary = await self.get(
                    repository_id, branch, github_name, gitflic_name
                )
                return repository_id, summary

        results = await asyncio.gather(*(worker(row) for row in rows))
        return dict(results)

    async def get(
        self,
        repository_id: int,
        branch: str,
        github_name: str | None,
        gitflic_name: str | None,
    ) -> CISummary:
        key = (repository_id, branch)
        cached = self._cache.get(key)
        if cached is not None:
            stored_at, summary = cached
            if self._ttl > 0 and (time.monotonic() - stored_at) < self._ttl:
                return summary
            self._cache.pop(key, None)

        github_result, gitflic_result = await asyncio.gather(
            self._lookup(self._github, github_name, branch, "github"),
            self._lookup(self._gitflic, gitflic_name, branch, "gitflic"),
        )
        summary = CISummary(
            github=str(github_result.get("status")),
            gitflic=str(gitflic_result.get("status")),
            aggregate=aggregate_ci([github_result, gitflic_result]),
        )
        self._cache[key] = (time.monotonic(), summary)
        return summary

    async def _lookup(
        self,
        client: GitHubClient | GitFlicClient,
        full_name: str | None,
        branch: str,
        provider: str,
    ) -> dict[str, object]:
        if full_name is None:
            return _not_configured(provider)
        result: dict[str, object] = await client.get_ci_status(full_name, branch)
        return result


__all__ = ["CIService", "CISummary", "aggregate_ci"]
