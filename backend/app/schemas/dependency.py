"""Pydantic schemas for dependency checks (SPEC §3.15, S25-004)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DependencyEcosystem = Literal["python", "node"]
DependencyPackageStatus = Literal["outdated", "current", "unknown", "ignored"]
DependencyPackageKind = Literal["exact", "range", "vcs", "path", "workspace"]
DependencySeverity = Literal["major", "minor", "patch"]
DependencyEcosystemStatus = Literal["ok", "no_manifest", "parse_error", "unavailable"]
DependencySource = Literal["registry", "cache", "mixed", "stale_cache", "none"]


class DependencyPackage(BaseModel):
    """One declared dependency and its registry comparison."""

    name: str
    declared: str
    current: str | None = None
    latest: str | None = None
    status: DependencyPackageStatus
    kind: DependencyPackageKind
    severity: DependencySeverity | None = None
    manifest_line: int | None = None
    manifest_section: str | None = None


class DependencyEcosystemReport(BaseModel):
    """Dependency report for one manifest/ecosystem."""

    ecosystem: DependencyEcosystem
    manifest: str | None = None
    status: DependencyEcosystemStatus
    source: DependencySource
    total: int = Field(default=0, ge=0)
    outdated: int = Field(default=0, ge=0)
    up_to_date: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)
    ignored: int = Field(default=0, ge=0)
    packages: list[DependencyPackage] = Field(default_factory=list)
    error: str | None = None


class DependencyReport(BaseModel):
    """API response for ``GET /repositories/{id}/dependencies``."""

    repository_id: int
    checked_at: datetime
    ecosystems: list[DependencyEcosystemReport] = Field(default_factory=list)
