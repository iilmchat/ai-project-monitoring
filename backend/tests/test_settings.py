"""Persistent settings API and config sync tests (S15-001)."""

from __future__ import annotations

from app.models.entities import AppSetting
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def test_settings_are_masked_and_persisted(
    app,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={
            "scan_roots": "/projects,/work",
            "github_token": "ghp_abcdefgh1234",
            "gitflic_token": "glpat-xyz9876",
            "webhook_secret": "webhook-secret-1234",
            "default_canonical_provider": "gitflic",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scan_roots"] == "/projects,/work"
    assert payload["github_token"] == "ghp_****1234"
    assert payload["gitflic_token"] == "glpa****9876"
    assert payload["webhook_secret"] == "webh****1234"
    assert "ghp_abcdefgh1234" not in response.text

    fetched = await client.get("/api/v1/settings")
    assert fetched.status_code == 200
    assert fetched.json()["github_token"] == "ghp_****1234"

    async with session_factory() as session:
        rows = {row.key: row.value for row in (await session.scalars(select(AppSetting))).all()}
    assert rows["scan_roots"] == "/projects,/work"
    assert rows["github_token"] == "ghp_abcdefgh1234"
    assert rows["default_canonical_provider"] == "gitflic"

    assert app.state.settings.scan_roots == "/projects,/work"
    assert app.state.settings.github_token == "ghp_abcdefgh1234"


async def test_settings_ignore_unknown_keys(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={"scan_roots": "/only", "database_url": "sqlite:///evil.db"},
    )

    assert response.status_code == 200
    assert response.json()["scan_roots"] == "/only"


async def test_settings_reject_invalid_provider(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={"default_canonical_provider": "bitbucket"},
    )
    assert response.status_code == 400


async def test_load_settings_from_db_into_config(
    app,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(AppSetting(key="github_token", value="ghp_loaded_from_db_4567"))
        session.add(AppSetting(key="scan_roots", value="/loaded"))
        await session.commit()

    await app.state.settings_service.load_into_config()

    assert app.state.settings.github_token == "ghp_loaded_from_db_4567"
    assert app.state.settings.scan_roots == "/loaded"
