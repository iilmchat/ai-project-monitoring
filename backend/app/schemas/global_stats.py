"""Pydantic schemas for the global tech-debt dashboard (SPEC §3.34)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

GlobalStatsRepositoryStatus = Literal["ok", "partial", "error"]
ProblemSeverity = Literal["critical", "high", "medium", "low", "unknown"]


class GlobalStatsScope(BaseModel):
    """How many repositories were considered and actually scanned."""

    repositories: int = Field(default=0, ge=0)
    tracked: int = Field(default=0, ge=0)
    scanned: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)


class GlobalVulnerabilitySummary(BaseModel):
    """CVE counts by severity across all tracked repositories."""

    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    unique_cves: int = Field(default=0, ge=0)


class ProblemTypeSummary(BaseModel):
    """One slice of the tech-debt pie chart."""

    type: str
    count: int = Field(default=0, ge=0)
    severity: ProblemSeverity


class GlobalStatsSummary(BaseModel):
    """Aggregated counters for the whole scope."""

    outdated_packages: int = Field(default=0, ge=0)
    unique_outdated_packages: int = Field(default=0, ge=0)
    vulnerabilities: GlobalVulnerabilitySummary = Field(
        default_factory=GlobalVulnerabilitySummary
    )
    dirty_files: int = Field(default=0, ge=0)
    diverged_branches: int = Field(default=0, ge=0)
    iac_issues: int = Field(default=0, ge=0)
    problem_types: list[ProblemTypeSummary] = Field(default_factory=list)


class GlobalRepositoryStats(BaseModel):
    """Tech-debt counters for one tracked repository."""

    repository_id: int
    name: str
    path: str
    status: GlobalStatsRepositoryStatus = "ok"
    stale: bool = False
    outdated_packages: int = Field(default=0, ge=0)
    vulnerabilities: GlobalVulnerabilitySummary = Field(
        default_factory=GlobalVulnerabilitySummary
    )
    dirty_files: int = Field(default=0, ge=0)
    diverged: bool = False
    iac_issues: int = Field(default=0, ge=0)
    problem_score: int = Field(default=0, ge=0)
    error: str | None = None


class TopProblematicRepository(BaseModel):
    """One entry of the top-5 bar chart."""

    repository_id: int
    name: str
    problem_score: int = Field(default=0, ge=0)


class GlobalStatsReport(BaseModel):
    """API response for ``GET /dashboard/global-stats``."""

    checked_at: datetime
    cached: bool = False
    scope: GlobalStatsScope = Field(default_factory=GlobalStatsScope)
    summary: GlobalStatsSummary = Field(default_factory=GlobalStatsSummary)
    repositories: list[GlobalRepositoryStats] = Field(default_factory=list)
    top_problematic: list[TopProblematicRepository] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error: str | None = None


class GlobalStatsAdviceRequest(BaseModel):
    """Optional language for the global AI report."""

    language: Literal["ru", "en"] = "ru"


class GlobalStatsPriority(BaseModel):
    """One prioritised action for the AI report."""

    title: str
    reason: str
    repository_id: int | None = None
    action: str


class GlobalStatsAdvice(BaseModel):
    """Markdown report plus a deterministic priority list."""

    generated_at: datetime
    summary: str
    priorities: list[GlobalStatsPriority] = Field(default_factory=list)
    model: str | None = None
    cached: bool = False


__all__ = [
    "GlobalRepositoryStats",
    "GlobalStatsAdvice",
    "GlobalStatsAdviceRequest",
    "GlobalStatsPriority",
    "GlobalStatsReport",
    "GlobalStatsRepositoryStatus",
    "GlobalStatsScope",
    "GlobalStatsSummary",
    "GlobalVulnerabilitySummary",
    "ProblemSeverity",
    "ProblemTypeSummary",
    "TopProblematicRepository",
]
