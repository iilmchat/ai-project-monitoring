"""Minimal read-only PyPI JSON API client (S25-003)."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

import httpx

from app.providers.package_versions import PackageVersionResult, RegistryLookupStatus

PYPI_API = "https://pypi.org"
USER_AGENT = "IIRuchating/0.5"

PypiLookupStatus = RegistryLookupStatus


class PypiClient:
    """Look up latest package versions without executing pip."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        base_url: str = PYPI_API,
        max_attempts: int = 3,
    ) -> None:
        self._timeout = max(timeout_seconds, 0.1)
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max(max_attempts, 1)

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        """Return the latest version from PyPI JSON API.

        HTTP errors are returned as a result object; they never escape as
        exceptions so one broken package cannot fail the whole report.
        """
        url = f"/pypi/{quote(package, safe='')}/json"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        for attempt in range(self._max_attempts):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=headers,
                ) as client:
                    response = await client.get(url)
            except httpx.TimeoutException:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return PackageVersionResult(
                    latest=None,
                    status="timeout",
                    error="timeout",
                )
            except httpx.HTTPError:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return PackageVersionResult(
                    latest=None,
                    status="unavailable",
                    error="registry_unavailable",
                )

            if response.status_code == 200:
                return self._parse_payload(response)
            if response.status_code == 404:
                return PackageVersionResult(latest=None, status="not_found")
            if response.status_code == 429:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return PackageVersionResult(
                    latest=None,
                    status="rate_limited",
                    error="rate_limited",
                )
            if response.status_code in {500, 502, 503, 504}:
                if attempt + 1 < self._max_attempts:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return PackageVersionResult(
                    latest=None,
                    status="unavailable",
                    error="registry_unavailable",
                )
            return PackageVersionResult(
                latest=None,
                status="unavailable",
                error="registry_unavailable",
            )

        return PackageVersionResult(
            latest=None,
            status="unavailable",
            error="registry_unavailable",
        )

    def _parse_payload(self, response: httpx.Response) -> PackageVersionResult:
        try:
            payload = response.json()
        except ValueError:
            return PackageVersionResult(
                latest=None,
                status="unavailable",
                error="registry_unavailable",
            )
        info = payload.get("info") if isinstance(payload, dict) else None
        latest = info.get("version") if isinstance(info, dict) else None
        if not isinstance(latest, str) or not latest:
            return PackageVersionResult(
                latest=None,
                status="unavailable",
                error="registry_unavailable",
            )
        return PackageVersionResult(
            latest=latest,
            status="ok",
            etag=response.headers.get("etag"),
        )


__all__ = [
    "PYPI_API",
    "PackageVersionResult",
    "PypiClient",
    "PypiLookupStatus",
    "RegistryLookupStatus",
]
