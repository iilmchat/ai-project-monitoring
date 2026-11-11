"""HTTP middleware."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)

AUTH_COOKIE_NAME = "iiruchating_session"
AUTH_EXEMPT_PATHS = frozenset(
    {
        "/api/v1/health",
        "/api/v1/metrics",
        "/api/v1/auth/login",
        "/api/v1/auth/reset-db",
    }
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every HTTP request as a structured event and propagate a request id."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid4().hex
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "http_request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Require a valid JWT for every API route except health/metrics/login."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path.rstrip("/") or "/"
        if (
            request.method == "OPTIONS"
            or not path.startswith("/api/v1")
            or path in AUTH_EXEMPT_PATHS
        ):
            return await call_next(request)

        settings = request.app.state.settings
        if not settings.auth_enabled:
            return await call_next(request)

        token = _token_from_request(request)
        if not token:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        auth_service = request.app.state.auth_service
        user = await auth_service.user_from_token(token)
        if user is None:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        request.state.user = user
        return await call_next(request)


def _token_from_request(request: Request) -> str | None:
    cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie:
        return cookie
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


__all__ = ["AUTH_COOKIE_NAME", "AUTH_EXEMPT_PATHS", "AuthMiddleware", "RequestLoggingMiddleware"]
