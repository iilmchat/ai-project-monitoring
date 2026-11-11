"""Team management and audit API (v1.3.0, Sprint 58)."""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_admin
from app.db.session import get_session
from app.models.entities import User
from app.schemas.audit import AuditActor, AuditEntryRead, AuditLogPage
from app.schemas.auth import (
    PasswordChangeRequest,
    PasswordOperationResponse,
    PasswordResetRequest,
    UserCreate,
    UserInviteResponse,
    UserRead,
    UserUpdate,
)
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter(tags=["team"])


def _auth(request: Request) -> AuthService:
    service: AuthService = request.app.state.auth_service
    return service


def _audit(request: Request) -> AuditService:
    service: AuditService = request.app.state.audit_service
    return service


def _read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.get("/users", response_model=list[UserRead])
async def list_users(
    request: Request,
    admin: Annotated[User | None, Depends(require_admin)],
) -> list[UserRead]:
    del admin
    return [_read(user) for user in await _auth(request).list_users()]


@router.post(
    "/users",
    response_model=UserInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreate,
    request: Request,
    admin: Annotated[User | None, Depends(require_admin)],
) -> UserInviteResponse:
    password = payload.password or secrets.token_urlsafe(9)
    try:
        user = await _auth(request).create_user(
            payload.username,
            password,
            role=payload.role,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="username_exists",
        ) from exc
    await _audit(request).log(
        admin.id if admin is not None else None,
        "user_created",
        "user",
        user.id,
        {"role": user.role, "username": user.username},
    )
    return UserInviteResponse(
        user=_read(user),
        temporary_password=None if payload.password else password,
    )


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    admin: Annotated[User | None, Depends(require_admin)],
) -> UserRead:
    auth = _auth(request)
    target = await auth.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")

    if admin is not None and admin.id == user_id:
        if payload.role is not None and payload.role != "admin":
            raise HTTPException(status_code=409, detail="cannot_demote_self")
        if payload.is_active is False:
            raise HTTPException(status_code=409, detail="cannot_demote_self")

    removes_admin = (
        target.role == "admin"
        and target.is_active
        and (
            (payload.role is not None and payload.role != "admin")
            or payload.is_active is False
        )
    )
    if removes_admin and await auth.count_admins() <= 1:
        raise HTTPException(status_code=409, detail="last_admin")

    updated = await auth.update_user(
        user_id,
        role=payload.role,
        is_active=payload.is_active,
        password=payload.password,
    )
    if updated is None:  # pragma: no cover - guarded by the lookup above
        raise HTTPException(status_code=404, detail="user_not_found")

    if payload.role is not None and payload.role != target.role:
        action = "role_changed"
        details: dict[str, Any] = {"from": target.role, "to": payload.role}
    else:
        action = "user_updated"
        details = {
            "is_active": updated.is_active,
            "password_reset": bool(payload.password),
        }
    await _audit(request).log(
        admin.id if admin is not None else None,
        action,
        "user",
        updated.id,
        {"username": updated.username, **details},
    )
    return _read(updated)


@router.patch("/users/me/password", response_model=PasswordOperationResponse)
async def change_own_password(
    payload: PasswordChangeRequest,
    request: Request,
) -> PasswordOperationResponse:
    """Change the password of the authenticated user (S61-004)."""
    auth = _auth(request)
    actor = current_user(request)
    if actor is None:
        # Local mode without auth has no request user; manage the bootstrap admin.
        settings = request.app.state.settings
        actor = await auth.get_by_username(settings.admin_username)
    if actor is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    if not auth.verify_password(payload.old_password, actor.hashed_password):
        raise HTTPException(status_code=400, detail="invalid_old_password")

    updated = await auth.update_user(actor.id, password=payload.new_password)
    if updated is None:  # pragma: no cover - guarded by the lookup above
        raise HTTPException(status_code=404, detail="user_not_found")
    await _audit(request).log(
        actor.id,
        "password_changed",
        "user",
        actor.id,
        {"username": updated.username},
    )
    return PasswordOperationResponse()


@router.post(
    "/users/{user_id}/reset-password",
    response_model=PasswordOperationResponse,
)
async def reset_user_password(
    user_id: int,
    payload: PasswordResetRequest,
    request: Request,
    admin: Annotated[User | None, Depends(require_admin)],
) -> PasswordOperationResponse:
    """Admin-only password reset for another account (S61-004)."""
    auth = _auth(request)
    target = await auth.get_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="user_not_found")

    updated = await auth.update_user(user_id, password=payload.new_password)
    if updated is None:  # pragma: no cover - guarded by the lookup above
        raise HTTPException(status_code=404, detail="user_not_found")
    await _audit(request).log(
        admin.id if admin is not None else None,
        "user_password_reset",
        "user",
        user_id,
        {"username": updated.username},
    )
    return PasswordOperationResponse()


@router.get("/audit", response_model=AuditLogPage)
async def list_audit(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User | None, Depends(require_admin)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogPage:
    del admin
    rows, total = await _audit(request).list_entries(
        session,
        limit=limit,
        offset=offset,
    )
    return AuditLogPage(
        items=[
            AuditEntryRead(
                id=entry.id,
                created_at=entry.created_at,
                user=AuditActor(
                    id=entry.user_id,
                    username=username,
                ),
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                details=entry.details or {},
            )
            for entry, username in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


__all__ = ["router"]
