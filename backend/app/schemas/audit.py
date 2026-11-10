"""Audit log API schemas (v1.3.0, Sprint 58)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditActor(BaseModel):
    id: int | None = None
    username: str | None = None


class AuditEntryRead(BaseModel):
    id: int
    created_at: datetime
    user: AuditActor
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogPage(BaseModel):
    items: list[AuditEntryRead] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


__all__ = ["AuditActor", "AuditEntryRead", "AuditLogPage"]
