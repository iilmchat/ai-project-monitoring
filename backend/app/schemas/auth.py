"""Auth and team-management schemas (v1.0.0 S47; roles — v1.3.0 S58)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["admin", "auditor"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class UserRead(BaseModel):
    id: int
    username: str
    role: UserRole = "auditor"
    is_active: bool = True
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    """Invite a teammate; a temporary password is generated when omitted."""

    username: str = Field(min_length=1, max_length=255)
    role: UserRole = "auditor"
    password: str | None = Field(default=None, min_length=8, max_length=1024)


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=1024)


class UserInviteResponse(BaseModel):
    user: UserRead
    temporary_password: str | None = None


class PasswordChangeRequest(BaseModel):
    """Self-service password change (S61-004)."""

    old_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class PasswordResetRequest(BaseModel):
    """Admin reset of another user's password (S61-004)."""

    new_password: str = Field(min_length=8, max_length=1024)


class PasswordOperationResponse(BaseModel):
    status: Literal["ok"] = "ok"


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class ResetDbRequest(BaseModel):
    """Explicit confirmation for the destructive local reset (S60-Fix-003)."""

    confirm: bool = False


class ResetDbResponse(BaseModel):
    status: Literal["ok"] = "ok"


__all__ = [
    "LoginRequest",
    "LoginResponse",
    "PasswordChangeRequest",
    "PasswordOperationResponse",
    "PasswordResetRequest",
    "ResetDbRequest",
    "ResetDbResponse",
    "UserCreate",
    "UserInviteResponse",
    "UserRead",
    "UserRole",
    "UserUpdate",
]
