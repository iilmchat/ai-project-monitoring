"""Single-user auth API (v1.0.0, Sprint 47)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.middleware import AUTH_COOKIE_NAME
from app.schemas.auth import LoginRequest, LoginResponse, UserRead
from app.services.auth_service import AuthService

router = APIRouter(tags=["auth"])


def _service(request: Request) -> AuthService:
    service: AuthService = request.app.state.auth_service
    return service


def _rate_key(request: Request, username: str) -> str:
    host = request.client.host if request.client is not None else "unknown"
    return f"{host}:{username.strip().lower()}"


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> LoginResponse:
    service = _service(request)
    settings = request.app.state.settings
    key = _rate_key(request, payload.username)
    if not service.allow_login(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too_many_attempts",
        )
    user = await service.authenticate(payload.username, payload.password)
    if user is None:
        service.record_login_failure(key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    service.clear_login_failures(key)
    token, expires_at = service.create_access_token(user)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=max(int(settings.auth_token_ttl_seconds), 60),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return LoginResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserRead(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
    )


@router.get("/auth/me", response_model=UserRead)
async def me(request: Request) -> UserRead:
    settings = request.app.state.settings
    if not settings.auth_enabled:
        return UserRead(id=0, username="local", role="admin", is_active=True)
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )
    return UserRead(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return None


__all__ = ["router"]
