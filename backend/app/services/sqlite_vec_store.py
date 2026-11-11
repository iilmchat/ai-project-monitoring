"""sqlite-vec storage for the desktop RAG index (S61-001).

The desktop build runs on SQLite, so pgvector is not available.  Chunks and
their embeddings live in a regular ``code_chunks`` table (embeddings are JSON,
which powers the pure-Python fallback) and, when the ``sqlite-vec`` extension
loads, in the ``vec_chunks`` virtual table for fast KNN search.

If the C extension is missing (for example a PyInstaller bundle without
``vec0.dll``), every operation degrades to the Python cosine fallback and the
service logs ``sqlite_vec_unavailable_fallback_to_python`` exactly once.
"""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from typing import Any

import structlog

from app.db.migrations import sqlite_path

logger = structlog.get_logger(__name__)

VEC_TABLE = "vec_chunks"
VEC_EXTENSIONS = ("vec0.dll", "vec0.so", "vec0.dylib")


class SqliteVecStore:
    """Small synchronous wrapper around a dedicated SQLite connection.

    A separate ``sqlite3`` connection is used instead of SQLAlchemy's async
    aiosqlite engine: the extension can only be loaded synchronously, and
    ``sqlite_vec.load`` does not accept an aiosqlite connection.
    """

    def __init__(self, database_url: str, dimensions: int) -> None:
        self._path = sqlite_path(database_url)
        self._dimensions = max(int(dimensions), 1)
        self._available: bool | None = None

    @property
    def available(self) -> bool:
        if self._available is None:
            connection = self._connect()
            if connection is None:
                self._available = False
            else:
                connection.close()
                self._available = True
        return self._available

    def search(
        self,
        vector: list[float],
        k: int,
        repository_ids: list[int] | None = None,
        language: str | None = None,
    ) -> list[tuple[int, float]] | None:
        """Return ``(rowid, cosine_distance)`` pairs or ``None`` on fallback."""
        connection = self._connect()
        if connection is None:
            return None
        sql = [
            "SELECT rowid, distance FROM vec_chunks",
            "WHERE embedding MATCH ?",
            "AND k = ?",
        ]
        params: list[object] = [_serialize(vector), max(int(k), 1)]
        if repository_ids:
            placeholders = ", ".join("?" for _ in repository_ids)
            sql.append(f"AND repository_id IN ({placeholders})")
            params.extend(int(value) for value in repository_ids)
        if language:
            sql.append("AND language = ?")
            params.append(language)
        try:
            rows = connection.execute(" ".join(sql), params).fetchall()
        except Exception as exc:  # pragma: no cover - depends on vec0 build
            logger.warning("sqlite_vec_search_failed", reason=str(exc))
            return None
        finally:
            connection.close()
        return [(int(row[0]), float(row[1])) for row in rows]

    def write(self, records: list[tuple[int, list[float], int, str]]) -> bool:
        """Insert ``(chunk_id, vector, repository_id, language)`` records."""
        if not records:
            return True
        connection = self._connect()
        if connection is None:
            return False
        try:
            connection.executemany(
                "DELETE FROM vec_chunks WHERE rowid = ?",
                [(rowid,) for rowid, *_ in records],
            )
            connection.executemany(
                "INSERT INTO vec_chunks"
                "(rowid, embedding, repository_id, language) VALUES (?,?,?,?)",
                [
                    (rowid, _serialize(vector), repository_id, language)
                    for rowid, vector, repository_id, language in records
                ],
            )
            connection.commit()
            return True
        except Exception as exc:  # pragma: no cover - depends on vec0 build
            connection.rollback()
            logger.warning("sqlite_vec_write_failed", reason=str(exc))
            return False
        finally:
            connection.close()

    def delete(self, chunk_ids: list[int]) -> bool:
        if not chunk_ids:
            return True
        connection = self._connect()
        if connection is None:
            return False
        try:
            connection.executemany(
                "DELETE FROM vec_chunks WHERE rowid = ?",
                [(int(chunk_id),) for chunk_id in chunk_ids],
            )
            connection.commit()
            return True
        except Exception as exc:  # pragma: no cover - depends on vec0 build
            connection.rollback()
            logger.warning("sqlite_vec_delete_failed", reason=str(exc))
            return False
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection | None:
        if self._path is None:
            self._fallback("not_sqlite")
            return None
        try:
            import sqlite_vec
        except Exception as exc:  # pragma: no cover - packaging guard
            self._fallback(f"import_failed:{exc}")
            return None

        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self._path, timeout=10)
            connection.enable_load_extension(True)
            try:
                _load_extension(connection, sqlite_vec)
            finally:
                connection.enable_load_extension(False)
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (VEC_TABLE,),
            ).fetchone()
            if exists is None:
                connection.execute(self._create_table_sql())
                connection.commit()
        except Exception as exc:
            self._fallback(str(exc))
            if connection is not None:
                connection.close()
            return None
        return connection

    def _create_table_sql(self) -> str:
        return (
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {VEC_TABLE} USING vec0("
            f"embedding float[{self._dimensions}] distance_metric=cosine, "
            "repository_id integer, language text)"
        )

    def _fallback(self, reason: str) -> None:
        if self._available is None:
            logger.warning(
                "sqlite_vec_unavailable_fallback_to_python",
                reason=reason,
                database_url=str(self._path),
            )
        self._available = False


def _load_extension(connection: sqlite3.Connection, sqlite_vec: Any) -> None:
    """Load ``vec0`` from the package, then from the frozen bundle if needed."""
    load = getattr(sqlite_vec, "load", None)
    if callable(load):
        try:
            load(connection)
            return
        except Exception:
            pass
    serialized_path = Path(str(sqlite_vec.loadable_path()))
    for candidate in _candidate_paths(serialized_path):
        if candidate.is_file():
            # SQLite appends the platform suffix itself when it is omitted.
            connection.load_extension(str(candidate.with_suffix("")))
            return
    raise FileNotFoundError(f"sqlite-vec extension not found near {serialized_path}")


def _candidate_paths(loadable_path: Path) -> list[Path]:
    candidates = [loadable_path.with_name(name) for name in VEC_EXTENSIONS]
    import sys

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        bundle_dir = Path(frozen_root) / "sqlite_vec"
        candidates.extend(bundle_dir / name for name in VEC_EXTENSIONS)
    return candidates


def _serialize(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


__all__ = ["VEC_EXTENSIONS", "VEC_TABLE", "SqliteVecStore"]
