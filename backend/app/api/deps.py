"""Role-based API dependencies (v1.3.0, Sprint 58)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.models.entities import User

ADMIN_ROLE = "admin"
AUDITOR_ROLE = "auditor"


def current_user(request: Request) -> User | None:
    """Return the authenticated user, if auth is enabled."""
    user = getattr(request.state, "user", None)
    return user if isinstance(user, User) else None


async def get_current_user(request: Request) -> User | None:
    """Return the current user or ``None`` in local (auth-disabled) mode."""
    if not request.app.state.settings.auth_enabled:
        return None
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )
    return user


async def require_admin(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User | None:
    """Allow only admins; local mode without auth is implicitly admin."""
    if user is None:
        return None
    if user.role != ADMIN_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="insufficient_role",
        )
    return user


def actor_id(request: Request) -> int | None:
    """Return the audit actor id (``None`` in local mode)."""
    user = current_user(request)
    return user.id if user is not None else None


__all__ = [
    "ADMIN_ROLE",
    "AUDITOR_ROLE",
    "actor_id",
    "current_user",
    "get_current_user",
    "require_admin",
]
