"""Minimal read-only npm registry client (S26-002)."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

import httpx

from app.providers.package_versions import PackageVersionResult, RegistryLookupStatus

NPM_REGISTRY = "https://registry.npmjs.org"
USER_AGENT = "IIRuchating/0.5"

NpmLookupStatus = RegistryLookupStatus


class NpmClient:
    """Look up latest package versions without executing npm/pnpm."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        base_url: str = NPM_REGISTRY,
        max_attempts: int = 3,
    ) -> None:
        self._timeout = max(timeout_seconds, 0.1)
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max(max_attempts, 1)

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        """Return the latest version from the npm registry.

        Scoped packages are encoded as ``@scope%2Fname``. HTTP errors are
        returned as result objects and never escape as exceptions.
        """
        encoded = quote(package, safe="@")
        url = f"/{encoded}/latest"
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
        latest = payload.get("version") if isinstance(payload, dict) else None
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
    "NPM_REGISTRY",
    "NpmClient",
    "NpmLookupStatus",
    "PackageVersionResult",
    "RegistryLookupStatus",
]
