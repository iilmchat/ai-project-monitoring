"""Role-based access tests (v1.3.0, Sprint 58)."""

from __future__ import annotations

from app.models.entities import User
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


async def _create_auditor(app: FastAPI, username: str = "auditor") -> User:
    return await app.state.auth_service.create_user(
        username,
        "auditor-pass",
        role="auditor",
    )


async def test_admin_token_contains_role_claim(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    payload = await _login(client, "admin", "admin")

    token = str(payload["access_token"])
    claims = app.state.auth_service.decode_token(token)
    assert claims is not None
    assert claims["role"] == "admin"
    assert payload["user"]["role"] == "admin"  # type: ignore[index]


async def test_auditor_can_read_but_cannot_mutate(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await _create_auditor(app)
    payload = await _login(client, "auditor", "auditor-pass")

    assert payload["user"]["role"] == "auditor"  # type: ignore[index]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "auditor"

    assert (await client.get("/api/v1/repositories")).status_code == 200
    assert (await client.get("/api/v1/dashboard")).status_code == 200

    action = await client.post(
        "/api/v1/repositories/1/actions/push",
        json={"confirm": True},
    )
    assert action.status_code == 403
    assert action.json()["detail"] == "insufficient_role"

    settings = await client.patch(
        "/api/v1/settings",
        json={"fetch_timeout": 31},
    )
    assert settings.status_code == 403

    scan = await client.post("/api/v1/scan", json={})
    assert scan.status_code == 403

    audit = await client.get("/api/v1/audit")
    assert audit.status_code == 403
    assert audit.json()["detail"] == "insufficient_role"


async def test_admin_can_list_users_and_invite(
    app: FastAPI,
    client: AsyncClient,
    session_factory,
) -> None:
    await _enable_auth(app)
    await _login(client, "admin", "admin")

    listed = await client.get("/api/v1/users")
    assert listed.status_code == 200
    assert any(item["role"] == "admin" for item in listed.json())

    created = await client.post(
        "/api/v1/users",
        json={"username": "viewer", "role": "auditor"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["role"] == "auditor"
    assert body["temporary_password"]

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.username == "viewer"))
    assert user is not None
    assert user.role == "auditor"


async def test_auditor_cannot_manage_users(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await _create_auditor(app)
    await _login(client, "auditor", "auditor-pass")

    response = await client.post(
        "/api/v1/users",
        json={"username": "other", "role": "auditor"},
    )
    assert response.status_code == 403


async def test_last_admin_cannot_be_demoted(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _enable_auth(app)
    await _login(client, "admin", "admin")

    me = await client.get("/api/v1/auth/me")
    admin_id = me.json()["id"]
    response = await client.patch(
        f"/api/v1/users/{admin_id}",
        json={"role": "auditor"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "cannot_demote_self"
