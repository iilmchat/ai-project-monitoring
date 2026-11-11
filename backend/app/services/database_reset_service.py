"""Recreate the local SQLite database from scratch (S60-Fix-003).

Used by ``POST /api/v1/auth/reset-db`` when the schema is so broken that the
user cannot log in.  Desktop mode only: the database file and its SQLite
journals are removed, migrations are replayed and the default admin is created
again.  Any other database backend is rejected.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.db.migrations import apply_migrations, sqlite_path
from app.services.auth_service import AuthService

logger = structlog.get_logger(__name__)

_SQLITE_SIDECARS = ("", "-wal", "-shm", "-journal")


class DatabaseResetError(Exception):
    """Reset is not possible for the configured database."""


class DatabaseResetService:
    """Delete the SQLite file, re-run migrations and bootstrap ``admin``."""

    def __init__(
        self,
        settings: Settings,
        engine: AsyncEngine,
        auth_service: AuthService,
    ) -> None:
        self._settings = settings
        self._engine = engine
        self._auth_service = auth_service

    async def reset(self) -> None:
        db_path = sqlite_path(self._settings.database_url)
        if db_path is None:
            raise DatabaseResetError("only_sqlite_supported")

        await self._engine.dispose()
        for suffix in _SQLITE_SIDECARS:
            Path(f"{db_path}{suffix}").unlink(missing_ok=True)

        await asyncio.to_thread(apply_migrations, self._settings.database_url)
        await self._auth_service.bootstrap_admin()
        logger.info(
            "database_reset",
            database_url=self._settings.database_url,
            username=self._settings.admin_username,
        )


__all__ = ["DatabaseResetError", "DatabaseResetService"]
