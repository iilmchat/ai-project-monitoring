"""Persistent application settings (S15-001)."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models.entities import AppSetting
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient

logger = structlog.get_logger(__name__)

ALLOWED_KEYS = frozenset(
    {
        "scan_roots",
        "github_token",
        "gitflic_token",
        "webhook_secret",
        "default_canonical_provider",
    }
)
SECRET_KEYS = frozenset({"github_token", "gitflic_token", "webhook_secret"})
CANONICAL_PROVIDERS = frozenset({"github", "gitflic"})


def mask_secret(value: str | None) -> str:
    """Mask a secret for API responses, keeping a short recognisable suffix."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


class SettingsService:
    """Read/write settings, with config.py values as fallback."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        *,
        github_client: GitHubClient | None = None,
        gitflic_client: GitFlicClient | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._github = github_client
        self._gitflic = gitflic_client

    async def get_settings(self) -> dict[str, str | None]:
        async with self._session_factory() as session:
            rows = (await session.scalars(select(AppSetting))).all()
        stored = {row.key: row.value for row in rows}
        values: dict[str, str | None] = {}
        for key in ALLOWED_KEYS:
            value = stored.get(key)
            if value is None:
                value = getattr(self._settings, key)
            values[key] = value
        return values

    async def load_into_config(self) -> dict[str, str | None]:
        values = await self.get_settings()
        self._apply(values)
        logger.info(
            "settings_loaded",
            keys=sorted(values),
            tokens_configured={
                "github": bool(values.get("github_token")),
                "gitflic": bool(values.get("gitflic_token")),
            },
        )
        return values

    async def update_settings(self, values: dict[str, Any]) -> dict[str, str | None]:
        updates: dict[str, str] = {}
        for key, value in values.items():
            if key not in ALLOWED_KEYS or value is None:
                continue
            if key == "default_canonical_provider" and value not in CANONICAL_PROVIDERS:
                raise ValueError(
                    "default_canonical_provider must be 'github' or 'gitflic'"
                )
            updates[key] = str(value).strip()

        if updates:
            async with self._session_factory() as session:
                existing = {
                    row.key: row
                    for row in (await session.scalars(select(AppSetting))).all()
                }
                for key, value in updates.items():
                    row = existing.get(key)
                    if row is None:
                        session.add(AppSetting(key=key, value=value))
                    else:
                        row.value = value
                await session.commit()

        merged = await self.get_settings()
        self._apply(merged)
        logger.info("settings_updated", keys=sorted(updates))
        return merged

    def _apply(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if key in ALLOWED_KEYS and value is not None:
                setattr(self._settings, key, value)
        if self._github is not None:
            self._github.set_token(self._settings.github_token)
        if self._gitflic is not None:
            self._gitflic.set_token(self._settings.gitflic_token)


__all__ = ["ALLOWED_KEYS", "SECRET_KEYS", "SettingsService", "mask_secret"]
