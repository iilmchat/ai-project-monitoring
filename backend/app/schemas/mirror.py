"""Mirror schemas (SPEC §3.8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.recommendation import RecommendationResponse

CanonicalProvider = Literal["github", "gitflic", "both"]


class MirrorProviderStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    full_name: str | None = None
    branch: str | None = None
    head_sha: str | None = None
    head_date: datetime | None = None
    private: bool | None = None
    checked_at: datetime | None = None


class MirrorStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repository_id: int
    github: MirrorProviderStatus | None = None
    gitflic: MirrorProviderStatus | None = None
    mirror_status: str
    canonical_provider: str
    mirror_expected: bool
    recommendations: list[RecommendationResponse] = Field(default_factory=list)
    checked_at: datetime


class MirrorPolicyUpdate(BaseModel):
    canonical_provider: CanonicalProvider | None = None
    mirror_expected: bool | None = None
    mirror_policy: str | None = None


class MirrorCandidatesResponse(BaseModel):
    github_only: list[dict[str, Any]] = Field(default_factory=list)
    gitflic_only: list[dict[str, Any]] = Field(default_factory=list)
    both: list[dict[str, Any]] = Field(default_factory=list)
    unknown: list[dict[str, Any]] = Field(default_factory=list)
