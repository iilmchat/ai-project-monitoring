"""Pydantic v2 schemas for repositories."""

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
    created_at: datetime
    updated_at: datetime


class RepositoryListResponse(BaseModel):
    """Paginated repository list."""

    items: list[RepositoryRead]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(ge=1)
