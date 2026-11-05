"""Settings schemas (S15-001)."""

from __future__ import annotations

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    scan_roots: str
    github_token: str
    gitflic_token: str
    webhook_secret: str
    default_canonical_provider: str


class SettingsUpdate(BaseModel):
    scan_roots: str | None = None
    github_token: str | None = None
    gitflic_token: str | None = None
    webhook_secret: str | None = None
    default_canonical_provider: str | None = None
