"""Pydantic schemas for security checks (SPEC §3.16, S28-004)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SecuritySeverity = Literal["critical", "high", "medium", "low", "unknown"]
SecurityVersionSource = Literal["exact", "lower_bound"]
SecurityEcosystemStatus = Literal["ok", "no_manifest", "parse_error", "unavailable"]
SecurityStatus = Literal["ok", "unavailable"]
UnknownPackageReason = Literal[
    "unresolved_range",
    "unsupported_kind",
    "registry_missing",
    "osv_unavailable",
]
SecretType = Literal[
    "aws_access_key",
    "aws_secret_key",
    "github_token",
    "jwt",
    "private_key",
]
SecretSeverity = Literal["high", "medium"]
SecretConfidence = Literal["high", "medium"]
SecretScanStatus = Literal["ok", "skipped", "partial", "unavailable"]


class SecurityVulnerability(BaseModel):
    """One advisory affecting one declared package version."""

    package: str
    version: str
    version_source: SecurityVersionSource
    osv_id: str
    cve_ids: list[str] = Field(default_factory=list)
    severity: SecuritySeverity
    cvss_score: float | None = None
    summary: str | None = None
    fixed_version: str | None = None
    references: list[str] = Field(default_factory=list)


class SecurityUnknownPackage(BaseModel):
    """A declared package that could not be checked reliably."""

    name: str
    reason: UnknownPackageReason


class SecurityEcosystemReport(BaseModel):
    """CVE report for one manifest/ecosystem."""

    ecosystem: Literal["python", "node"]
    manifest: str
    status: SecurityEcosystemStatus
    total_packages: int = Field(default=0, ge=0)
    packages_checked: int = Field(default=0, ge=0)
    vulnerabilities: list[SecurityVulnerability] = Field(default_factory=list)
    unknown_packages: list[SecurityUnknownPackage] = Field(default_factory=list)
    error: str | None = None


class SecretFinding(BaseModel):
    """One potential secret found in the working directory."""

    file: str
    line: int = Field(ge=1)
    type: SecretType
    severity: SecretSeverity
    confidence: SecretConfidence
    preview: str


class SecretScanReport(BaseModel):
    """Result of the regex secret scan."""

    status: SecretScanStatus = "ok"
    files_scanned: int = Field(default=0, ge=0)
    truncated: bool = False
    findings: list[SecretFinding] = Field(default_factory=list)
    error: str | None = None


class SecuritySummary(BaseModel):
    """Aggregated counts across requested ecosystems and secrets."""

    total_packages: int = Field(default=0, ge=0)
    packages_checked: int = Field(default=0, ge=0)
    vulnerable: int = Field(default=0, ge=0)
    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)
    secrets_found: int = Field(default=0, ge=0)


class SecurityReport(BaseModel):
    """API response for ``GET /repositories/{id}/security``."""

    repository_id: int
    checked_at: datetime
    status: SecurityStatus = "ok"
    summary: SecuritySummary = Field(default_factory=SecuritySummary)
    ecosystems: list[SecurityEcosystemReport] = Field(default_factory=list)
    secrets: SecretScanReport = Field(default_factory=SecretScanReport)
    error: str | None = None


__all__ = [
    "SecretConfidence",
    "SecretFinding",
    "SecretScanReport",
    "SecretScanStatus",
    "SecretSeverity",
    "SecretType",
    "SecurityEcosystemReport",
    "SecurityEcosystemStatus",
    "SecurityReport",
    "SecuritySeverity",
    "SecurityStatus",
    "SecuritySummary",
    "SecurityUnknownPackage",
    "SecurityVersionSource",
    "SecurityVulnerability",
    "UnknownPackageReason",
]
