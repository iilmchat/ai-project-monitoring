"""Shared provider value objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class BranchResult:
    """Result of a branch lookup at an external provider.

    ``found=False`` means the provider answered 404 (repository/branch absent);
    ``error`` means the provider could not be queried (token/network/5xx).
    """

    sha: str | None = None
    date: datetime | None = None
    found: bool = True
    error: str | None = None
    rate_limited: bool = False

    @property
    def available(self) -> bool:
        return self.error is None and self.found


@dataclass(frozen=True, slots=True)
class ProviderRepo:
    """Normalized repository entry returned by provider listing APIs."""

    provider: str
    full_name: str
    private: bool
    default_branch: str
    url: str | None = None

    @property
    def name(self) -> str:
        return self.full_name.rsplit("/", 1)[-1].removesuffix(".git").lower()


__all__ = ["BranchResult", "ProviderRepo"]
