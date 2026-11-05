"""Pydantic v2 schemas for repositories and their local status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryRead(BaseModel):
    """Public representation of a repository."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    alias: str | None = None
    tracked: bool
    github_full_name: str | None = None
    gitflic_full_name: str | None = None
    canonical_provider: str = "github"
    mirror_expected: bool = True
    mirror_policy: str = "github_to_gitflic"
    created_at: datetime
    updated_at: datetime


class RepositoryListResponse(BaseModel):
    """Paginated repository list."""

    items: list[RepositoryRead]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)


class DirtyCountsResponse(BaseModel):
    """Uncommitted change counters (SPEC §3.4)."""

    model_config = ConfigDict(from_attributes=True)

    modified: int = Field(default=0, ge=0)
    staged: int = Field(default=0, ge=0)
    untracked: int = Field(default=0, ge=0)
    conflicted: int = Field(default=0, ge=0)


class RepositoryStatusResponse(BaseModel):
    """Canonical local status of a repository (SPEC §3.4)."""

    model_config = ConfigDict(from_attributes=True)

    repository_id: int
    path: str
    branch: str | None = None
    head_sha: str | None = None
    head_subject: str | None = None
    head_date: datetime | None = None
    upstream: str | None = None
    ahead: int = Field(default=0, ge=0)
    behind: int = Field(default=0, ge=0)
    state: str
    dirty: DirtyCountsResponse = Field(default_factory=DirtyCountsResponse)
    detached: bool = False
    remote_status: str = "stale"
    error: str | None = None
    checked_at: datetime


class RefreshRequest(BaseModel):
    """Body for ``POST /repositories/{id}/refresh``."""

    fetch: bool = True


class CommitInfoResponse(BaseModel):
    """Commit metadata (SPEC §3.5)."""

    model_config = ConfigDict(from_attributes=True)

    sha: str
    subject: str
    author: str
    date: datetime


class CompareResponse(BaseModel):
    """Result of comparing ``head`` against ``base`` (SPEC §3.5)."""

    model_config = ConfigDict(from_attributes=True)

    ahead: int = Field(ge=0)
    behind: int = Field(ge=0)
    status: str
    commits: list[CommitInfoResponse] = Field(default_factory=list)
