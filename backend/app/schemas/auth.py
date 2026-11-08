"""Auth schemas (v1.0.0, Sprint 47)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class UserRead(BaseModel):
    id: int
    username: str
    is_active: bool = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


__all__ = ["LoginRequest", "LoginResponse", "UserRead"]
