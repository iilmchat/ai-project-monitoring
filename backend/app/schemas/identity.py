"""Schemas for remote repository identity (S37-001)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DuplicateRepository(BaseModel):
    id: int
    path: str
    name: str


class DuplicateGroup(BaseModel):
    remote_url: str
    repositories: list[DuplicateRepository] = Field(default_factory=list)


class DuplicatesResponse(BaseModel):
    groups: list[DuplicateGroup] = Field(default_factory=list)
    checked: int = Field(default=0, ge=0)


__all__ = ["DuplicateGroup", "DuplicateRepository", "DuplicatesResponse"]
