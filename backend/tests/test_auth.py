"""Single-user authentication tests (S47)."""

from __future__ import annotations

from app.models.entities import User
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select


async def _enable_auth(app: FastAPI) -> None:
    app.state.settings.auth_enabled = True
    await app.state.auth_service.bootstrap_admin()


async def test_health_is_public_when_auth_enabled(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["db_ok"] is True


async def test_login_sets_cookie_and_protects_api(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)

    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login.status_code == 200, login.text
    payload = login.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["username"] == "admin"
    assert "access_token" in payload
    assert "iiruchating_session" in login.cookies

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    protected = await client.get("/api/v1/repositories")
    assert protected.status_code == 200

    client.cookies.clear()
    unauthorized = await client.get("/api/v1/repositories")
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"] == "unauthorized"


async def test_login_accepts_bearer_token(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    token = login.json()["access_token"]
    client.cookies.clear()

    response = await client.get(
        "/api/v1/repositories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


async def test_invalid_password_is_rejected(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_credentials"


async def test_login_rate_limit(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401
    limited = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert limited.status_code == 429
    assert limited.json()["detail"] == "too_many_attempts"


async def test_logout_clears_session(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    after = await client.get("/api/v1/auth/me")
    assert after.status_code == 401


async def test_bootstrap_creates_only_one_admin(
    app: FastAPI,
    session_factory,
) -> None:
    app.state.settings.auth_enabled = True
    assert await app.state.auth_service.bootstrap_admin() is True
    assert await app.state.auth_service.bootstrap_admin() is False

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(User))
    assert count == 1
