"""Dashboard response schemas (SPEC §3.6)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.repository import RepositoryRead, RepositoryStatusResponse


class DashboardSummary(BaseModel):
    """Aggregated counters shown on the dashboard."""

    total: int = Field(ge=0)
    clean: int = Field(ge=0)
    needs_attention: int = Field(ge=0)
    untracked: int = Field(ge=0)
    stale: int = Field(ge=0)
    errors: int = Field(ge=0)


class DashboardRepository(RepositoryRead):
    """Repository row with its last known status (may be missing)."""

    status: RepositoryStatusResponse | None = None


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    repositories: list[DashboardRepository] = Field(default_factory=list)
