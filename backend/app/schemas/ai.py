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
    cached: bool = False
    generated_at: datetime


class ConflictResolveRequest(BaseModel):
    """Payload for ``POST /repositories/{id}/ai/resolve-conflict``."""

    file_path: str = Field(min_length=1, max_length=1024)
    language: Literal["ru", "en"] = "ru"
    refresh: bool = False


class ConflictResolveResponse(BaseModel):
    """Result of AI conflict resolution (full file text, not written)."""

    repository_id: int
    file_path: str
    resolved: str
    blocks: int = Field(default=0, ge=0)
    provider: str
    model: str
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    cached: bool = False
    generated_at: datetime


class ReleaseNotesRequest(BaseModel):
    """Payload for ``POST /repositories/{id}/ai/release-notes``."""

    from_tag: str = Field(min_length=1, max_length=256)
    to_tag: str = Field(default="HEAD", min_length=1, max_length=256)
    language: Literal["ru", "en"] = "ru"
    refresh: bool = False


class ReleaseNotesResponse(BaseModel):
    """Result of AI release notes generation."""

    repository_id: int
    from_tag: str
    to_tag: str
    changelog: str
    commits: int = Field(default=0, ge=0)
    provider: str
    model: str
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    cached: bool = False
    generated_at: datetime


class CodeReviewRequest(BaseModel):
    """Payload for ``POST /repositories/{id}/ai/code-review``."""

    language: Literal["ru", "en"] = "ru"
    refresh: bool = False


class CodeReviewResponse(BaseModel):
    """Result of AI code review."""

    repository_id: int
    review: str
    source: Literal["llm"] = "llm"
    provider: str
    model: str
    files_reviewed: int = Field(default=0, ge=0)
    diff_chars: int = Field(default=0, ge=0)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    cached: bool = False
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


class DashboardAdviceRequest(BaseModel):
    """Optional language for the AI dashboard digest."""

    language: Literal["ru", "en"] = "ru"


class DashboardAdvice(BaseModel):
    """Result of ``POST /ai/dashboard-advice``."""

    advice: str
    cached: bool = False
    model: str | None = None
    generated_at: datetime
    stats: dict[str, int] = Field(default_factory=dict)


class AgentTaskRequest(BaseModel):
    """Optional language for the generated agent task."""

    language: Literal["ru", "en"] = "ru"


class AgentTask(BaseModel):
    """Result of ``POST /repositories/{id}/ai/agent-task``."""

    task: str
    model: str | None = None
    generated_at: datetime


class LLMTestResponse(BaseModel):
    """Result of ``POST /settings/llm/test``."""

    status: Literal["ok", "error"]
    latency_ms: float = Field(default=0, ge=0)
    error: str | None = None


__all__ = [
    "AgentTask",
    "AgentTaskRequest",
    "CodeReviewRequest",
    "CodeReviewResponse",
    "CommitMessageSuggestion",
    "ConflictResolveRequest",
    "ConflictResolveResponse",
    "CveExplainRequest",
    "CveExplanation",
    "DashboardAdvice",
    "DashboardAdviceRequest",
    "LLMTestResponse",
    "ReleaseNotesRequest",
    "ReleaseNotesResponse",
]
