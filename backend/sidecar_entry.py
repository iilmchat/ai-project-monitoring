"""PyInstaller entry point for the Tauri sidecar (S48-001, S59-Fix).

The sidecar always runs in desktop mode: SQLite under the per-user app-data
directory, bound to 127.0.0.1 on a port chosen by the Tauri shell.

Database migrations are applied programmatically through Alembic before
uvicorn starts.  Shelling out to ``alembic`` is not an option inside a
PyInstaller one-file bundle, so ``alembic.command.upgrade`` is invoked with an
explicit ``Config`` pointing at the bundled ``alembic`` directory.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IIRuchating desktop backend")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", default="")
    return parser.parse_args()


def _redirect_logs(data_dir: Path) -> None:
    log_path = data_dir / "backend.log"
    stream = log_path.open("a", encoding="utf-8", buffering=1)
    sys.stdout = stream
    sys.stderr = stream
    logging.basicConfig(stream=stream, level=logging.INFO, format="%(message)s")


def _bundle_root() -> Path:
    """Directory that holds resources bundled by PyInstaller."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parent


def _sqlite_path(database_url: str) -> Path | None:
    """Return the on-disk SQLite path for ``database_url`` when there is one."""
    if not database_url.startswith("sqlite") or "///" not in database_url:
        return None
    raw_path = database_url.split("///", 1)[1]
    if not raw_path or raw_path.startswith(":memory:"):
        return None
    return Path(raw_path).expanduser()


def _table_names(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {str(row[0]) for row in rows if not str(row[0]).startswith("sqlite_")}


def _column_names(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row[1]) for row in rows}


def _stamped_revision(db_path: Path) -> str | None:
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


def _detect_legacy_revision(db_path: Path, tables: set[str]) -> str | None:
    """Map a pre-Alembic SQLite schema to the newest matching revision.

    Desktop builds up to v1.3.0 created the schema with ``create_all`` and
    never wrote ``alembic_version``.  Stamping such a database before running
    ``upgrade head`` avoids replaying migrations whose tables already exist.
    """
    if "sast_cache" in tables:
        return "014"
    if "audit_log" in tables:
        return "013"
    if "users" in tables:
        if "role" in _column_names(db_path, "users"):
            return "013"
        return "012"
    if "ai_provider_profiles" in tables:
        if "provider_type" in _column_names(db_path, "ai_provider_profiles"):
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
        if "branch" in _column_names(db_path, "repository_status"):
            return "002"
        return "001"
    if "repositories" in tables:
        return "001"
    return None


def _alembic_config(database_url: str) -> Any:
    from alembic.config import Config

    root = _bundle_root()
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


def _apply_migrations(database_url: str) -> None:
    """Run ``alembic upgrade head`` and log the resulting revision."""
    from alembic import command

    logger = logging.getLogger("sidecar.migrations")
    db_path = _sqlite_path(database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    config = _alembic_config(database_url)

    if db_path is not None and _stamped_revision(db_path) is None:
        tables = _table_names(db_path)
        if tables:
            revision = _detect_legacy_revision(db_path, tables)
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

    logger.info("alembic_migrations_started database_url=%s", database_url)
    try:
        command.upgrade(config, "head")
    except Exception:
        logger.exception("alembic_migrations_failed database_url=%s", database_url)
        raise

    if db_path is not None:
        logger.info(
            "alembic_migrations_completed revision=%s",
            _stamped_revision(db_path),
        )
    else:
        logger.info("alembic_migrations_completed")


def main() -> None:
    args = _parse_args()
    os.environ["TAURI_MODE"] = "true"
    if args.data_dir:
        os.environ["TAURI_DATA_DIR"] = args.data_dir
    os.environ.setdefault("AUTH_ENABLED", "true")

    from app.config import Settings

    settings = Settings()
    data_dir = Path(settings.tauri_data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _redirect_logs(data_dir)
    _apply_migrations(settings.database_url)

    import uvicorn
    from app.main import create_app

    application = create_app(settings)
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=max(args.port, 1),
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
