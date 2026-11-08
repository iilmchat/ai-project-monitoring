"""Schemas for AI provider profiles (S39-001)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AIProviderRead(BaseModel):
    id: int
    name: str
    base_url: str
    api_key: str
    model_name: str
    is_active: bool
    created_at: datetime


class AIProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=1024)
    model_name: str = Field(min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)


class AIProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=1024)
    model_name: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)


__all__ = ["AIProviderCreate", "AIProviderRead", "AIProviderUpdate"]
