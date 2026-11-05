"""Pydantic v2 schemas for discovery scans."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScanRequest(BaseModel):
    """Body for ``POST /api/v1/scan``; all fields are optional."""

    roots: list[str] | None = Field(
        default=None,
        description="Roots to scan; defaults to SCAN_ROOTS from settings.",
    )
    depth: int | None = Field(
        default=None,
        ge=0,
        le=32,
        description="Maximum depth below each root; defaults to SCAN_DEPTH.",
    )
    force: bool = Field(
        default=False,
        description="Reserved: re-emit already known repositories (no-op in Sprint 1).",
    )


class ScanStarted(BaseModel):
    """Immediate response to a scan request (the scan runs in background)."""

    scan_id: int
    started_at: datetime


class ScanResponse(BaseModel):
    """Scan run state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    found: int = Field(validation_alias="found_count")
    added: int = Field(validation_alias="added_count")
    skipped: int = Field(validation_alias="skipped_count")
    errors: list[str] = Field(default_factory=list)
