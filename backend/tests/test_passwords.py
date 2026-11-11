"""Password change and admin reset tests (S61-004)."""

from __future__ import annotations

from app.models.entities import AuditLog, User
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select


async def _enable_auth(app: FastAPI) -> None:
    app.state.settings.auth_enabled = True
    await app.state.auth_service.bootstrap_admin()


async def _login(
    client: AsyncClient,
    username: str,
    password: str,
) -> dict[str, object]:
    client.cookies.clear()
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _actions(session_factory) -> list[str]:
    async with session_factory() as session:
        return [str(value) for value in await session.scalars(select(AuditLog.action))]


async def test_change_own_password_rejects_wrong_old_password(
    app: FastAPI,
    client: AsyncClient,
    session_factory,
) -> None:
    await _enable_auth(app)
    await _login(client, "admin", "admin")

    response = await client.patch(
        "/api/v1/users/me/password",
        json={"old_password": "not-the-password", "new_password": "new-secret"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_old_password"
    assert "password_changed" not in await _actions(session_factory)
    # The original credentials still work.
    await _login(client, "admin", "admin")


async def test_change_own_password_updates_credentials_and_audit(
    app: FastAPI,
    client: AsyncClient,
    session_factory,
) -> None:
    await _enable_auth(app)
    await _login(client, "admin", "admin")

    response = await client.patch(
        "/api/v1/users/me/password",
        json={"old_password": "admin", "new_password": "new-secret"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    client.cookies.clear()
    old = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert old.status_code == 401
    await _login(client, "admin", "new-secret")
    assert "password_changed" in await _actions(session_factory)


async def test_auditor_cannot_reset_other_password(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await app.state.auth_service.create_user(
        "auditor",
        "auditor-pass",
        role="auditor",
    )
    admin = await app.state.auth_service.get_by_username("admin")
    assert admin is not None
    await _login(client, "auditor", "auditor-pass")

    response = await client.post(
        f"/api/v1/users/{admin.id}/reset-password",
        json={"new_password": "hijacked-pass"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient_role"
    await _login(client, "admin", "admin")


async def test_admin_resets_user_password_and_audits(
    app: FastAPI,
    client: AsyncClient,
    session_factory,
) -> None:
    await _enable_auth(app)
    await app.state.auth_service.create_user(
        "auditor",
        "auditor-pass",
        role="auditor",
    )
    target = await app.state.auth_service.get_by_username("auditor")
    assert target is not None
    await _login(client, "admin", "admin")

    response = await client.post(
        f"/api/v1/users/{target.id}/reset-password",
        json={"new_password": "reset-secret"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    await _login(client, "auditor", "reset-secret")
    assert "user_password_reset" in await _actions(session_factory)

    async with session_factory() as session:
        stored = await session.scalar(select(User).where(User.id == target.id))
    assert stored is not None
    assert app.state.auth_service.verify_password(
        "reset-secret",
        stored.hashed_password,
    )


async def test_admin_reset_rejects_unknown_user(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await _login(client, "admin", "admin")

    response = await client.post(
        "/api/v1/users/999/reset-password",
        json={"new_password": "reset-secret"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "user_not_found"
