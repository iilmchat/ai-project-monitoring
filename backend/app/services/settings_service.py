"""Persistent application settings (S15-001, extended in S43-001)."""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models.entities import AppSetting
from app.providers.gitflic_client import GitFlicClient
from app.providers.github_client import GitHubClient
from app.services.mirror_scheduler import MirrorScheduler
from app.services.notification_service import NotificationService
from app.services.remote_service import RemoteService
from app.services.status_service import StatusCache, StatusService

logger = structlog.get_logger(__name__)

ALLOWED_KEYS = frozenset(
    {
        "scan_roots",
        "github_token",
        "gitflic_token",
        "webhook_secret",
        "default_canonical_provider",
        "llm_enabled",
        "llm_base_url",
        "llm_model",
        "llm_api_key",
        "llm_timeout_seconds",
        "llm_max_diff_chars",
        "llm_allow_remote",
        "telegram_bot_token",
        "telegram_chat_id",
        "notifications_enabled",
        "fetch_timeout",
        "status_ttl_seconds",
        "mirror_poll_interval_seconds",
        "embedding_dimensions",
        "rag_chunk_size",
        "rag_chunk_overlap",
    }
)
SECRET_KEYS = frozenset(
    {
        "github_token",
        "gitflic_token",
        "webhook_secret",
        "llm_api_key",
        "telegram_bot_token",
    }
)
BOOL_KEYS = frozenset({"llm_enabled", "llm_allow_remote", "notifications_enabled"})
INT_KEYS = frozenset(
    {
        "llm_timeout_seconds",
        "llm_max_diff_chars",
        "fetch_timeout",
        "status_ttl_seconds",
        "mirror_poll_interval_seconds",
        "embedding_dimensions",
        "rag_chunk_size",
        "rag_chunk_overlap",
    }
)
CANONICAL_PROVIDERS = frozenset({"github", "gitflic"})
_TRUTHY = frozenset({"1", "true", "yes", "on"})


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
        remote_service: RemoteService | None = None,
        status_cache: StatusCache | None = None,
        status_service: StatusService | None = None,
        mirror_scheduler: MirrorScheduler | None = None,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._github = github_client
        self._gitflic = gitflic_client
        self._remote_service = remote_service
        self._status_cache = status_cache
        self._status_service = status_service
        self._mirror_scheduler = mirror_scheduler
        self._notifications = notification_service

    async def get_settings(self) -> dict[str, str | None]:
        async with self._session_factory() as session:
            rows = (await session.scalars(select(AppSetting))).all()
        stored = {row.key: row.value for row in rows}
        values: dict[str, str | None] = {}
        for key in ALLOWED_KEYS:
            value = stored.get(key)
            if value is None:
                value = self._config_value(key)
            values[key] = value
        return values

    async def seed_from_config(self) -> bool:
        """Persist config.py/.env values on first start.

        ``app_settings`` used to be populated only after the first PATCH, which
        made ``.env`` values invisible in the UI and easy to overwrite. The seed
        runs only when the table is completely empty, so an existing database is
        never modified.
        """
        async with self._session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(AppSetting)
            )
            if count:
                return False
            for key in sorted(ALLOWED_KEYS):
                session.add(AppSetting(key=key, value=self._config_value(key)))
            await session.commit()
        logger.info("settings_seeded_from_config", keys=sorted(ALLOWED_KEYS))
        return True

    async def load_into_config(self) -> dict[str, str | None]:
        await self.seed_from_config()
        values = await self.get_settings()
        self._apply(values)
        logger.info(
            "settings_loaded",
            keys=sorted(values),
            tokens_configured={
                "github": bool(values.get("github_token")),
                "gitflic": bool(values.get("gitflic_token")),
                "telegram": bool(values.get("telegram_bot_token")),
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
            if key in {"llm_api_key", "telegram_bot_token"} and not str(value).strip():
                # Empty secret means "keep the current value".
                continue
            if key == "llm_base_url":
                url = str(value).strip()
                if url and not url.startswith(("http://", "https://")):
                    raise ValueError("llm_base_url must start with http:// or https://")
                updates[key] = url
                continue
            if key in BOOL_KEYS:
                updates[key] = (
                    "true" if str(value).strip().lower() in _TRUTHY else "false"
                )
                continue
            if key in INT_KEYS:
                try:
                    number = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key} must be an integer") from exc
                if number < 0 or (number == 0 and key != "rag_chunk_overlap"):
                    raise ValueError(f"{key} must be positive")
                updates[key] = str(number)
                continue
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

    def _config_value(self, key: str) -> str | None:
        raw = getattr(self._settings, key)
        if key in BOOL_KEYS:
            return "true" if bool(raw) else "false"
        if key in INT_KEYS:
            try:
                return str(int(float(raw)))
            except (TypeError, ValueError):
                return None
        return str(raw) if raw is not None else None

    def _apply(self, values: dict[str, str | None]) -> None:
        for key, value in values.items():
            if key not in ALLOWED_KEYS or value is None:
                continue
            if key in BOOL_KEYS:
                setattr(self._settings, key, value.strip().lower() in _TRUTHY)
            elif key in INT_KEYS:
                try:
                    setattr(self._settings, key, int(value))
                except (TypeError, ValueError):
                    continue
            else:
                setattr(self._settings, key, value)
        if self._github is not None:
            self._github.set_token(self._settings.github_token)
        if self._gitflic is not None:
            self._gitflic.set_token(self._settings.gitflic_token)
        if self._remote_service is not None:
            self._remote_service.set_timeout(self._settings.fetch_timeout)
        if self._status_cache is not None:
            self._status_cache.set_ttl(self._settings.status_ttl_seconds)
        if self._status_service is not None:
            self._status_service.set_ttl(self._settings.status_ttl_seconds)
        if self._mirror_scheduler is not None:
            self._mirror_scheduler.set_interval(
                self._settings.mirror_poll_interval_seconds
            )
        if self._notifications is not None:
            self._notifications.configure(
                enabled=self._settings.notifications_enabled,
                bot_token=self._settings.telegram_bot_token,
                chat_id=self._settings.telegram_chat_id,
            )


__all__ = ["ALLOWED_KEYS", "SECRET_KEYS", "SettingsService", "mask_secret"]
