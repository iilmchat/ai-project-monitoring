"""PyInstaller entry point for the Tauri sidecar (S48-001).

The sidecar always runs in desktop mode: SQLite under the per-user app-data
directory, bound to 127.0.0.1 on a port chosen by the Tauri shell.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import multiprocessing
import os
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


def _init_database(settings: Any) -> None:
    import app.models.entities  # noqa: F401  (register ORM metadata)
    from app.db.base import Base
    from app.db.session import build_engine

    database_url = settings.database_url

    async def run() -> None:
        engine = build_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    asyncio.run(run())


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
    _init_database(settings)

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
