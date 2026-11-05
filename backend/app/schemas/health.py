"""Health endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    git_version: str | None = None
    scan_roots: list[str]
    db_ok: bool
