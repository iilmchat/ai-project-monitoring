"""Mutation request/response schemas (Sprint 10)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ActionRequest(BaseModel):
    """Mutations require an explicit confirmation flag."""

    confirm: bool = False
    repository_id: int | None = None
    message: str | None = None


class BulkActionRequest(BaseModel):
    """Optional scope for bulk fetch/sync operations."""

    repo_ids: list[int] | None = None


class DependencyUpdateRequest(BaseModel):
    """Explicit confirmed dependency update for one repository."""

    confirm: bool = False
    ecosystem: Literal["python", "node"]


class BulkDependencyUpdateRequest(BaseModel):
    """Explicit confirmed dependency update for many repositories."""

    confirm: bool = False
    ecosystem: Literal["python", "node"]
    repo_ids: list[int] | None = None


class ActionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int | None = None
    action: str
    command: str
    status: str
    output: str | None = None
    error: str | None = None
    duration_ms: int = 0
    exit_code: int | None = None
    actor: str
    created_at: datetime
