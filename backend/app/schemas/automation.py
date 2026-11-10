"""Automation config generation schemas (v1.3.0, Sprint 59)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AutomationTool = Literal["dependabot", "renovate"]


class AutomationGenerateRequest(BaseModel):
    tool: AutomationTool


class AutomationConfigResponse(BaseModel):
    tool: AutomationTool
    path: str
    content: str
    content_hash: str
    ecosystems: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "AutomationConfigResponse",
    "AutomationGenerateRequest",
    "AutomationTool",
]
