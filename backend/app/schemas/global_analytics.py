"""Pydantic schemas for global dependency analytics (SPEC §3.19)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class VersionDistribution(BaseModel):
    """Projects that declare a particular package version."""

    version: str
    projects: list[str] = Field(default_factory=list)


class GlobalDependencyPackage(BaseModel):
    """One package aggregated across all tracked repositories."""

    name: str
    latest_version: str | None = None
    distribution: list[VersionDistribution] = Field(default_factory=list)
    versions_count: int = Field(default=0, ge=0)
    projects_count: int = Field(default=0, ge=0)
    unification_needed: bool = False


class GlobalDependencySummary(BaseModel):
    repositories: int = Field(default=0, ge=0)
    packages: int = Field(default=0, ge=0)
    unification_candidates: int = Field(default=0, ge=0)


class UnificationAdviceRequest(BaseModel):
    """Ask the LLM for advice on unifying one package."""

    ecosystem: Literal["python", "node"]
    package: str


class UnificationAdvice(BaseModel):
    """LLM advice for a package that is declared in different versions."""

    ecosystem: Literal["python", "node"]
    package: str
    advice: str
    cached: bool = False
    model: str | None = None
    generated_at: datetime


class GlobalDependencyReport(BaseModel):
    """API response for ``GET /dashboard/global-dependencies``."""

    checked_at: datetime
    ecosystems: dict[
        Literal["python", "node"], list[GlobalDependencyPackage]
    ] = Field(default_factory=dict)
    summary: GlobalDependencySummary = Field(
        default_factory=GlobalDependencySummary
    )
    error: str | None = None


__all__ = [
    "GlobalDependencyPackage",
    "GlobalDependencyReport",
    "GlobalDependencySummary",
    "UnificationAdvice",
    "UnificationAdviceRequest",
    "VersionDistribution",
]
