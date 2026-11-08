"""Persistent settings API and config sync tests (S15-001)."""

from __future__ import annotations

from app.models.entities import AppSetting
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeLLM:
    async def test_connection(self) -> tuple[bool, float, str | None]:
        return True, 123.4, None


async def test_llm_test_endpoint(
    app,
    client: AsyncClient,
) -> None:
    app.state.llm_service = FakeLLM()

    response = await client.post("/api/v1/settings/llm/test")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "latency_ms": 123.4, "error": None}


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


async def test_empty_db_is_seeded_from_config(
    app,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app.state.settings.telegram_chat_id = "-100123456"
    app.state.settings.fetch_timeout = 45
    app.state.settings.notifications_enabled = False

    assert await app.state.settings_service.seed_from_config() is True

    async with session_factory() as session:
        rows = {
            row.key: row.value
            for row in (await session.scalars(select(AppSetting))).all()
        }
    assert rows["telegram_chat_id"] == "-100123456"
    assert rows["fetch_timeout"] == "45"
    assert rows["notifications_enabled"] == "false"
    assert "telegram_bot_token" in rows

    payload = (await client.get("/api/v1/settings")).json()
    assert payload["telegram_chat_id"] == "-100123456"
    assert payload["fetch_timeout"] == 45
    assert payload["notifications_enabled"] is False

    # A second seed must not duplicate or overwrite rows.
    assert await app.state.settings_service.seed_from_config() is False


async def test_new_settings_apply_to_runtime_services(
    app,
    client: AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={
            "telegram_bot_token": "123456:abcdefghijklmnop",
            "telegram_chat_id": "-100777",
            "notifications_enabled": True,
            "fetch_timeout": 55,
            "status_ttl_seconds": 90,
            "mirror_poll_interval_seconds": 120,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["telegram_bot_token"] == "1234****mnop"
    assert payload["telegram_chat_id"] == "-100777"
    assert payload["notifications_enabled"] is True
    assert payload["fetch_timeout"] == 55
    assert payload["status_ttl_seconds"] == 90
    assert payload["mirror_poll_interval_seconds"] == 120
    assert "123456:abcdefghijklmnop" not in response.text

    assert app.state.settings.fetch_timeout == 55
    assert app.state.settings.status_ttl_seconds == 90
    assert app.state.settings.mirror_poll_interval_seconds == 120
    assert app.state.remote_service.timeout_seconds == 55
    assert app.state.status_service.ttl_seconds == 90
    assert app.state.mirror_scheduler.interval_seconds == 120
    assert app.state.notification_service.enabled is True
    assert app.state.notification_service.telegram_configured is True
