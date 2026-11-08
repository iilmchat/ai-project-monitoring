"""Schemas for AI provider profiles (S39-001, S43-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProviderType = Literal["openai_compatible", "gigachat"]
AuthType = Literal["api_key", "oauth"]


class AIProviderRead(BaseModel):
    id: int
    name: str
    base_url: str
    api_key: str
    model_name: str
    is_active: bool
    created_at: datetime
    provider_type: ProviderType = "openai_compatible"
    auth_type: AuthType = "api_key"
    client_id: str = ""
    has_client_secret: bool = False
    oauth_scope: str | None = None
    oauth_expires_at: datetime | None = None


class AIProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=1024)
    model_name: str = Field(min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)
    provider_type: ProviderType = "openai_compatible"
    auth_type: AuthType = "api_key"
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, max_length=2048)
    oauth_scope: str | None = Field(default=None, max_length=128)


class AIProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=1024)
    model_name: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, max_length=2048)
    provider_type: ProviderType | None = None
    auth_type: AuthType | None = None
    client_id: str | None = Field(default=None, max_length=255)
    client_secret: str | None = Field(default=None, max_length=2048)
    oauth_scope: str | None = Field(default=None, max_length=128)


class GigaChatAuthRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=255)
    client_secret: str = Field(min_length=1, max_length=2048)
    scope: str = Field(default="GIGACHAT_API_PERS", max_length=128)
    model_name: str = Field(default="GigaChat", min_length=1, max_length=255)
    profile_name: str = Field(default="GigaChat", min_length=1, max_length=255)
    base_url: str | None = Field(default=None, max_length=1024)
    activate: bool = False


class GigaChatAuthResponse(BaseModel):
    profile_id: int
    status: Literal["ok"] = "ok"
    expires_at: datetime
    model_name: str


__all__ = [
    "AIProviderCreate",
    "AIProviderRead",
    "AIProviderUpdate",
    "AuthType",
    "GigaChatAuthRequest",
    "GigaChatAuthResponse",
    "ProviderType",
]
