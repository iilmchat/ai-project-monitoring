"""CI status schemas (S11-001)."""

from __future__ import annotations

from pydantic import BaseModel


class ProviderCIStatus(BaseModel):
    provider: str
    status: str
    conclusion: str | None = None
    url: str | None = None


class CIStatusResponse(BaseModel):
    repository_id: int
    branch: str
    github: ProviderCIStatus
    gitflic: ProviderCIStatus
    aggregate: str
