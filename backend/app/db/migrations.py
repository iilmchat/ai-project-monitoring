"""Alembic bootstrap and SQLite schema repair helpers.

The desktop sidecar applies migrations before uvicorn starts, and the
``POST /auth/reset-db`` endpoint re-runs them after recreating the SQLite file.
Both paths share the logic below.

S60-Fix-001 adds a targeted repair for databases that claim revision 013 but
still lack ``users.role`` (the v1.1.0 → v1.3.0 upgrade left such schemas in a
half-migrated state).  The database is never dropped: only the missing column is
added and the default admin row is marked as ``admin``.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("sidecar.migrations")

USERS_ROLE_REVISION = "013"


def bundle_root() -> Path:
    """Directory that holds resources bundled by PyInstaller."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


def sqlite_path(database_url: str) -> Path | None:
    """Return the on-disk SQLite path for ``database_url`` when there is one."""
    if not database_url.startswith("sqlite") or "///" not in database_url:
        return None
    raw_path = database_url.split("///", 1)[1]
    if not raw_path or raw_path.startswith(":memory:"):
        return None
    return Path(raw_path).expanduser()


def table_names(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {str(row[0]) for row in rows if not str(row[0]).startswith("sqlite_")}


def column_names(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row[1]) for row in rows}


def stamped_revision(db_path: Path) -> str | None:
    """Return the revision stored in ``alembic_version`` (if any)."""
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
        if exists is None:
            return None
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return str(row[0]) if row else None


def detect_legacy_revision(db_path: Path, tables: set[str]) -> str | None:
    """Map a pre-Alembic SQLite schema to the newest matching revision.

    Desktop builds up to v1.3.0 created the schema with ``create_all`` and
    never wrote ``alembic_version``.  Stamping such a database before running
    ``upgrade head`` avoids replaying migrations whose tables already exist.
    """
    if db_path is None or not tables:
        return None
    if "code_chunks" in tables:
        return "015"
    if "sast_cache" in tables:
        return "014"
    if "audit_log" in tables:
        return "013"
    if "users" in tables:
        if "role" in column_names(db_path, "users"):
            return "013"
        return "012"
    if "ai_provider_profiles" in tables:
        if "provider_type" in column_names(db_path, "ai_provider_profiles"):
            return "010"
        return "009"
    if "ai_cache" in tables:
        return "008"
    if "security_cache" in tables:
        return "007"
    if "dependency_cache" in tables:
        return "006"
    if "app_settings" in tables:
        return "005"
    if "action_log" in tables:
        return "004"
    if "repository_mirror_status" in tables:
        return "003"
    if "repository_status" in tables:
        if "branch" in column_names(db_path, "repository_status"):
            return "002"
        return "001"
    if "repositories" in tables:
        return "001"
    return None


def alembic_config(database_url: str) -> Any:
    from alembic.config import Config

    root = bundle_root()
    ini_path = root / "alembic.ini"
    script_location = root / "alembic"
    if not ini_path.is_file() or not script_location.is_dir():
        raise FileNotFoundError(
            f"Alembic assets are missing from the bundle: {ini_path}, {script_location}"
        )

    config = Config(str(ini_path))
    config.set_main_option("script_location", str(script_location))
    config.set_main_option("sqlalchemy.url", database_url)
    config.attributes["database_url"] = database_url
    # Keep the sidecar log stream configured by ``_redirect_logs``.
    config.attributes["skip_logging_config"] = True
    return config


def repair_users_role(db_path: Path) -> bool:
    """Add ``users.role`` when the schema is stuck before migration 013.

    Returns ``True`` when the column was added.  The database itself is kept
    intact: only the missing column and the default admin row are touched.
    """
    if not db_path.exists() or "users" not in table_names(db_path):
        return False
    if "role" in column_names(db_path, "users"):
        return False
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'admin'"
        )
        connection.execute("UPDATE users SET role = 'admin' WHERE username = 'admin'")
        connection.commit()
    return True


def _is_missing_users_role(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "no such column" in message and "users.role" in message


def _repair_if_needed(db_path: Path | None, revision: str | None) -> bool:
    """Repair ``users.role`` only when Alembic already claims revision 013+.

    For older revisions migration 013 itself adds the column, so repairing
    first would make the migration fail with a duplicate column.
    """
    if db_path is None or revision is None or revision < USERS_ROLE_REVISION:
        return False
    return repair_users_role(db_path)


def apply_migrations(database_url: str) -> None:
    """Run ``alembic upgrade head`` and repair a half-applied roles migration."""
    from alembic import command

    db_path = sqlite_path(database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    config = alembic_config(database_url)

    revision = stamped_revision(db_path) if db_path is not None else None
    if db_path is not None and revision is None:
        tables = table_names(db_path)
        if tables:
            revision = detect_legacy_revision(db_path, tables)
            if revision is None:
                raise RuntimeError(
                    "Existing database has no alembic_version and its schema "
                    "cannot be mapped to a known migration revision"
                )
            logger.info(
                "alembic_stamp_legacy revision=%s database_url=%s",
                revision,
                database_url,
            )
            command.stamp(config, revision)

    if _repair_if_needed(db_path, revision):
        logger.info(
            "db_schema_repaired reason=missing_users_role database_url=%s",
            database_url,
        )

    logger.info("alembic_migrations_started database_url=%s", database_url)
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        if (
            db_path is None
            or not _is_missing_users_role(exc)
            or not _repair_if_needed(db_path, revision)
        ):
            logger.exception("alembic_migrations_failed database_url=%s", database_url)
            raise
        logger.warning(
            "db_schema_repair_started reason=%s database_url=%s",
            exc,
            database_url,
        )
        logger.info(
            "db_schema_repaired reason=upgrade_error database_url=%s",
            database_url,
        )
        command.upgrade(config, "head")

    if db_path is not None:
        logger.info(
            "alembic_migrations_completed revision=%s",
            stamped_revision(db_path),
        )
    else:
        logger.info("alembic_migrations_completed")


__all__ = [
    "alembic_config",
    "apply_migrations",
    "bundle_root",
    "column_names",
    "detect_legacy_revision",
    "repair_users_role",
    "sqlite_path",
    "stamped_revision",
    "table_names",
]
