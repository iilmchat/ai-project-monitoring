"""Shared result type for package registry lookups (PyPI/npm)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RegistryLookupStatus = Literal[
    "ok",
    "not_found",
    "rate_limited",
    "unavailable",
    "timeout",
]


@dataclass(frozen=True, slots=True)
class PackageVersionResult:
    """Latest version lookup result for one package."""

    latest: str | None
    status: RegistryLookupStatus
    error: str | None = None
    etag: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "ok"


__all__ = ["PackageVersionResult", "RegistryLookupStatus"]
