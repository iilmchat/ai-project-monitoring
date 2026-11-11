"""PyInstaller entry point for the Tauri sidecar (S48-001, S59-Fix).

The sidecar always runs in desktop mode: SQLite under the per-user app-data
directory, bound to 127.0.0.1 on a port chosen by the Tauri shell.

Database migrations are applied programmatically through Alembic before
uvicorn starts.  Shelling out to ``alembic`` is not an option inside a
PyInstaller one-file bundle, so ``alembic.command.upgrade`` is invoked with an
explicit ``Config`` pointing at the bundled ``alembic`` directory.

The migration and schema-repair logic lives in ``app.db.migrations`` so the
``POST /auth/reset-db`` API can reuse it.  S60-Fix-001 heals databases that
claim revision 013 but still miss ``users.role`` instead of deleting data.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
import os
import sys
from pathlib import Path

from app.db.migrations import apply_migrations, detect_legacy_revision

# Backwards-compatible names used by the migration tests.
_apply_migrations = apply_migrations


def _detect_legacy_revision(db_path: Path, tables: set[str]) -> str | None:
    return detect_legacy_revision(db_path, tables)


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
