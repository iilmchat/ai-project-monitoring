"""Sidecar Alembic bootstrap tests (S59-Fix)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from app.db.base import Base
from app.db.session import build_engine
from sidecar_entry import _apply_migrations, _detect_legacy_revision


def _url(db_path: Path) -> str:
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"


def _tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {str(row[0]) for row in rows if not str(row[0]).startswith("sqlite_")}


def _revision(db_path: Path) -> str | None:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    return str(row[0]) if row else None


async def _create_all(url: str) -> None:
    import app.models  # noqa: F401  (register ORM metadata)

    engine = build_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _execute(url: str, *statements: str) -> None:
    engine = build_engine(url)
    try:
        async with engine.begin() as connection:
            for statement in statements:
                await connection.exec_driver_sql(statement)
    finally:
        await engine.dispose()


def test_fresh_database_migrates_to_head(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "iiruchating.db"

    _apply_migrations(_url(db_path))

    assert db_path.exists()
    assert {"repositories", "users", "audit_log", "sast_cache"} <= _tables(db_path)
    assert _revision(db_path) == "014"


def test_legacy_v110_database_is_stamped_and_upgraded(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    asyncio.run(_create_all(_url(db_path)))
    # Emulate the reported v1.1.0 desktop database: schema created by
    # ``create_all``, no ``alembic_version`` table, ``users`` never created.
    asyncio.run(
        _execute(
            _url(db_path),
            "DROP TABLE audit_log",
            "DROP TABLE sast_cache",
            "DROP TABLE users",
        )
    )
    assert "alembic_version" not in _tables(db_path)

    _apply_migrations(_url(db_path))

    tables = _tables(db_path)
    assert {"users", "audit_log", "sast_cache"} <= tables
    assert _revision(db_path) == "014"
    with sqlite3.connect(db_path) as connection:
        user_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(users)")
        }
    assert "role" in user_columns


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idempotent.db"

    _apply_migrations(_url(db_path))
    _apply_migrations(_url(db_path))

    assert "users" in _tables(db_path)
    assert _revision(db_path) == "014"


def test_legacy_revision_detection(tmp_path: Path) -> None:
    db_path = tmp_path / "detect.db"
    asyncio.run(_create_all(_url(db_path)))
    tables = _tables(db_path)

    assert _detect_legacy_revision(db_path, tables) == "014"

    # Without users/audit/sast the newest SQLite marker is 010 (011 is
    # PostgreSQL-only), so users is created while replaying 012.
    legacy_tables = tables - {"users", "audit_log", "sast_cache"}
    assert _detect_legacy_revision(db_path, legacy_tables) == "010"
