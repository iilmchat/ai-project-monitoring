"""Pydantic schemas for AI features (SPEC §3.18, S32)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CommitMessageSuggestion(BaseModel):
    """Result of ``POST /repositories/{id}/ai/commit-message``."""

    repository_id: int
    message: str
    source: Literal["llm"] = "llm"
    provider: str
    model: str
    truncated: bool = False
    diff_chars: int = Field(default=0, ge=0)
    files_changed: int = Field(default=0, ge=0)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime


class CveExplainRequest(BaseModel):
    """Payload for ``POST /repositories/{id}/ai/cve-explain``."""

    cve_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=4000)


class CveExplanation(BaseModel):
    """Result of CVE explanation."""

    explanation: str
    cached: bool = False
    model: str | None = None
    generated_at: datetime


__all__ = [
    "CommitMessageSuggestion",
    "CveExplainRequest",
    "CveExplanation",
]
