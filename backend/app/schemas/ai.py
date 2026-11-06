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


__all__ = ["CommitMessageSuggestion"]
