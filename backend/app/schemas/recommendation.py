"""Recommendation schemas (SPEC §3.7)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RecommendationResponse(BaseModel):
    """A suggested (never auto-executed) command."""

    model_config = ConfigDict(from_attributes=True)

    action: str
    reason: str
    command: str
    category: str = "local"
