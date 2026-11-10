"""Audit log tests (v1.3.0, Sprint 58)."""

from __future__ import annotations

from app.models.entities import AuditLog
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select


async def _login_admin(app: FastAPI, client: AsyncClient) -> None:
    app.state.settings.auth_enabled = True
    await app.state.auth_service.bootstrap_admin()
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200, response.text


async def test_settings_update_is_audited(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _login_admin(app, client)

    updated = await client.patch(
        "/api/v1/settings",
        json={"fetch_timeout": 42, "notifications_enabled": False},
    )
    assert updated.status_code == 200, updated.text

    audit = await client.get("/api/v1/audit")
    assert audit.status_code == 200
    payload = audit.json()
    entry = next(
        item for item in payload["items"] if item["action"] == "settings_updated"
    )
    assert entry["user"]["username"] == "admin"
    assert entry["entity_type"] == "settings"
    assert set(entry["details"]["keys"]) == {
        "fetch_timeout",
        "notifications_enabled",
    }
    # Values (including secrets) must not be stored.
    assert "fetch_timeout" not in entry["details"] or isinstance(
        entry["details"].get("fetch_timeout"), str
    )


async def test_role_change_is_audited(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    await _login_admin(app, client)
    created = await client.post(
        "/api/v1/users",
        json={"username": "promoted", "role": "auditor", "password": "strong-pass"},
    )
    assert created.status_code == 201
    user_id = created.json()["user"]["id"]

    updated = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"role": "admin"},
    )
    assert updated.status_code == 200, updated.text

    audit = (await client.get("/api/v1/audit")).json()
    actions = [item["action"] for item in audit["items"]]
    assert "user_created" in actions
    role_entry = next(
        item for item in audit["items"] if item["action"] == "role_changed"
    )
    assert role_entry["entity_type"] == "user"
    assert role_entry["entity_id"] == str(user_id)
    assert role_entry["details"]["from"] == "auditor"
    assert role_entry["details"]["to"] == "admin"


async def test_audit_pagination_and_newest_first(
    app: FastAPI,
    client: AsyncClient,
    session_factory,
) -> None:
    await _login_admin(app, client)
    await app.state.audit_service.log(None, "scan_started", "scan", 1, {})
    await app.state.audit_service.log(None, "dep_update", "repository", 2, {})

    first = await client.get("/api/v1/audit", params={"limit": 1, "offset": 0})
    assert first.status_code == 200
    body = first.json()
    assert body["limit"] == 1
    assert body["total"] == 2
    assert body["items"][0]["action"] == "dep_update"

    second = await client.get("/api/v1/audit", params={"limit": 1, "offset": 1})
    assert second.json()["items"][0]["action"] == "scan_started"

    async with session_factory() as session:
        rows = (await session.scalars(select(AuditLog))).all()
    assert len(rows) == 2


async def test_audit_details_are_sanitized(
    app: FastAPI,
) -> None:
    entry = await app.state.audit_service.log(
        None,
        "settings_updated",
        "settings",
        None,
        {
            "keys": ["github_token"],
            "token": object(),
        },
    )

    assert entry.details["keys"] == ["github_token"]
    assert "token" not in entry.details
