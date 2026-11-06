"""Pydantic schemas for repository insights (SPEC §3.17, S29)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

InsightsStatus = Literal[
    "ok",
    "partial",
    "no_branch",
    "shallow_clone",
    "timeout",
    "unavailable",
]


class InsightsWindow(BaseModel):
    """Time window used for commit frequency and hotspots."""

    days: int = Field(ge=1, le=365)
    since: str
    until: str
    branch: str | None = None
    hotspots_days: int = Field(default=90, ge=1)


class Hotspot(BaseModel):
    """One frequently changed file."""

    file: str
    count: int = Field(ge=0)


class CommitFrequencyPoint(BaseModel):
    """Commits on one day; gaps are filled with zeroes."""

    date: str
    count: int = Field(ge=0)


class InsightsSummary(BaseModel):
    """Aggregates for the commit-frequency window."""

    commits: int = Field(default=0, ge=0)
    per_day: float = Field(default=0.0, ge=0)
    per_week: float = Field(default=0.0, ge=0)


class InsightsReport(BaseModel):
    """API response for ``GET /repositories/{id}/insights``."""

    repository_id: int
    checked_at: datetime
    status: InsightsStatus = "ok"
    window: InsightsWindow
    hotspots: list[Hotspot] = Field(default_factory=list)
    commit_frequency: list[CommitFrequencyPoint] = Field(default_factory=list)
    summary: InsightsSummary = Field(default_factory=InsightsSummary)
    error: str | None = None


__all__ = [
    "CommitFrequencyPoint",
    "Hotspot",
    "InsightsReport",
    "InsightsStatus",
    "InsightsSummary",
    "InsightsWindow",
]
