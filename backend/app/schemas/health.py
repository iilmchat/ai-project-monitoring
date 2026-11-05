"""Health endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str
    git_version: str | None = None
    scan_roots: list[str]
    db_ok: bool
    providers: dict[str, str] = Field(default_factory=dict)
