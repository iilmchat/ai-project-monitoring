"""SAST report schemas (v1.3.0, Sprint 59)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SastSeverity = Literal["critical", "high", "medium", "low", "unknown"]
SastToolStatus = Literal["ok", "unavailable", "error"]
SastStatus = Literal["ok", "partial", "unavailable"]


class SastFinding(BaseModel):
    """One normalized static-analysis finding."""

    tool: str
    rule_id: str
    severity: SastSeverity
    confidence: str | None = None
    category: str | None = None
    cwe: str | None = None
    file: str
    line: int = Field(ge=1)
    column: int | None = None
    message: str
    snippet: str | None = None
    fingerprint: str


class SastToolReport(BaseModel):
    """Outcome of one SAST tool invocation."""

    name: str
    status: SastToolStatus
    version: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    error: str | None = None


class SastSummary(BaseModel):
    total: int = Field(default=0, ge=0)
    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    unknown: int = Field(default=0, ge=0)


class SastReport(BaseModel):
    """API response for ``GET /repositories/{id}/sast``."""

    repository_id: int
    checked_at: datetime
    status: SastStatus
    tools: list[SastToolReport] = Field(default_factory=list)
    summary: SastSummary = Field(default_factory=SastSummary)
    findings: list[SastFinding] = Field(default_factory=list)
    truncated: bool = False
    error: str | None = None
    cached: bool = False


class SastExplainRequest(BaseModel):
    """Ask the LLM to explain one SAST finding."""

    rule_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=2000)
    file: str = Field(min_length=1, max_length=1024)
    line: int = Field(ge=1)
    snippet: str = Field(default="", max_length=4000)


class SastExplanation(BaseModel):
    """LLM explanation for a SAST finding."""

    explanation: str
    cached: bool = False
    model: str | None = None
    generated_at: datetime


__all__ = [
    "SastExplainRequest",
    "SastExplanation",
    "SastFinding",
    "SastReport",
    "SastSeverity",
    "SastStatus",
    "SastSummary",
    "SastToolReport",
    "SastToolStatus",
]
