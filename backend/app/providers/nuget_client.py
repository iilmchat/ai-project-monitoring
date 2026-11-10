"""Minimal read-only NuGet V3 flat-container client (S57-002).

The client mirrors :mod:`app.providers.pypi_client` and
:mod:`app.providers.npm_client`: it never raises on HTTP/network errors and
always returns a :class:`PackageVersionResult`. Only stable SemVer versions are
considered "latest".
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote

import httpx

from app.providers.package_versions import PackageVersionResult, RegistryLookupStatus

NUGET_API = "https://api.nuget.org"
USER_AGENT = "IIRuchating/1.3"

NuGetLookupStatus = RegistryLookupStatus
_VERSION_CORE_RE = re.compile(r"^v?(\d+(?:\.\d+){0,3})")


class NuGetClient:
    """Look up latest NuGet package versions without running ``dotnet``."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        base_url: str = NUGET_API,
        max_attempts: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = max(timeout_seconds, 0.1)
        self._base_url = base_url.rstrip("/")
        self._max_attempts = max(max_attempts, 1)
        self._transport = transport

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        """Return the latest stable version from the NuGet flat container.

        Package ids are case-insensitive and must be lower-cased in the URL.
        Prerelease versions are ignored; if no stable version exists the
        package is reported as ``not_found`` (and the caller shows ``unknown``).
        """
        normalized = package.strip().lower()
        if not normalized:
            return PackageVersionResult(latest=None, status="not_found")
        url = f"/v3-flatcontainer/{quote(normalized, safe='')}/index.json"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        for attempt in range(self._max_attempts):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=headers,
                    transport=self._transport,
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
        versions = payload.get("versions") if isinstance(payload, dict) else None
        if not isinstance(versions, list):
            return PackageVersionResult(
                latest=None,
                status="unavailable",
                error="registry_unavailable",
            )

        stable = [
            (self._version_key(item), item)
            for item in versions
            if isinstance(item, str) and self._is_stable(item)
        ]
        if not stable:
            return PackageVersionResult(latest=None, status="not_found")
        latest = max(stable, key=lambda entry: entry[0])[1]
        return PackageVersionResult(
            latest=latest,
            status="ok",
            etag=response.headers.get("etag"),
        )

    @staticmethod
    def _is_stable(version: str) -> bool:
        core = version.strip()
        if not core or not _VERSION_CORE_RE.match(core):
            return False
        return "-" not in core

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        match = _VERSION_CORE_RE.match(version.strip())
        if match is None:
            return (0,)
        parts = [int(part) for part in match.group(1).split(".")]
        while len(parts) < 4:
            parts.append(0)
        return tuple(parts)


__all__ = [
    "NUGET_API",
    "NuGetClient",
    "NuGetLookupStatus",
    "PackageVersionResult",
    "RegistryLookupStatus",
]
