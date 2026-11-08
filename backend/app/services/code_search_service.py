"""RAG code search over tracked repositories (SPEC §3.26, S44).

The service is intentionally PostgreSQL-only: embeddings are stored in a
pgvector column and searched with the cosine-distance operator. On SQLite the
API returns ``503 rag_unavailable`` and the rest of the application keeps
working.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.base import utcnow
from app.models.entities import Repository
from app.schemas.code_search import (
    CodeIndexStatus,
    CodeSearchResponse,
    CodeSearchResult,
)
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".md": "markdown",
    ".mdx": "markdown",
}
IGNORED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "target",
        "vendor",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        ".next",
        "coverage",
    }
)
IGNORED_FILES = frozenset(
    {
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "composer.lock",
    }
)
SECRET_PATTERN = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)"
    r"(\s*[:=]\s*)(['\"]?)([^'\"\s,;]+)"
)
MAX_SNIPPET_CHARS = 400


class RagUnavailableError(Exception):
    """RAG is disabled (SQLite) or the embedding model is unavailable."""

    def __init__(self, code: str = "rag_unavailable", message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


class RagBusyError(Exception):
    """An indexing run is already in progress."""


@dataclass(frozen=True, slots=True)
class _Chunk:
    path: str
    start_line: int
    end_line: int
    language: str
    content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class _RepoInfo:
    id: int
    path: str
    alias: str | None
    github_full_name: str | None


class CodeSearchService:
    """Index repository code into pgvector and search it semantically."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        llm_service: LLMService,
        *,
        database_url: str,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._llm = llm_service
        self._database_url = database_url
        self._running = False
        self._last_indexed_at: datetime | None = None
        self._errors: list[str] = []

    @property
    def available(self) -> bool:
        return self._database_url.lower().startswith(
            ("postgresql", "postgres")
        )

    async def index(
        self,
        repository_ids: list[int] | None = None,
        *,
        force: bool = False,
    ) -> CodeIndexStatus:
        self._require_postgres()
        if self._running:
            raise RagBusyError("indexing already running")
        self._running = True
        self._errors = []
        indexed_chunks = 0
        try:
            async with self._session_factory() as session:
                statement = select(Repository).where(Repository.tracked.is_(True))
                if repository_ids:
                    statement = statement.where(Repository.id.in_(repository_ids))
                repositories = list(
                    (await session.scalars(statement.order_by(Repository.id))).all()
                )
                for repository in repositories:
                    try:
                        indexed_chunks += await self._index_repository(
                            session, repository, force=force
                        )
                        await session.commit()
                    except Exception as exc:
                        await session.rollback()
                        self._errors.append(f"{repository.path}: {exc}")
                        logger.warning(
                            "rag_index_repository_failed",
                            repository_id=repository.id,
                            error=str(exc),
                        )
            self._last_indexed_at = utcnow()
        finally:
            self._running = False
        return await self.status()

    async def search(
        self,
        query: str,
        *,
        repository_ids: list[int] | None = None,
        limit: int = 5,
        min_score: float = 0.2,
        language: str | None = None,
    ) -> CodeSearchResponse:
        self._require_postgres()
        started = time.perf_counter()
        vectors = await self._embed([query])
        query_vector = vectors[0]

        params: dict[str, object] = {
            "embedding": json.dumps(query_vector),
            "limit": limit,
            "min_score": min_score,
        }
        filters = ["r.tracked = true"]
        if language:
            filters.append("c.language = :language")
            params["language"] = language
        if repository_ids:
            placeholders = []
            for index, repo_id in enumerate(repository_ids):
                name = f"repo_{index}"
                placeholders.append(f":{name}")
                params[name] = repo_id
            filters.append(f"c.repository_id IN ({', '.join(placeholders)})")

        sql = text(
            f"""
            SELECT c.repository_id,
                   r.alias,
                   r.path AS repository_path,
                   r.github_full_name,
                   c.path,
                   c.start_line,
                   c.end_line,
                   c.language,
                   c.content,
                   1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM code_chunks c
            JOIN repositories r ON r.id = c.repository_id
            WHERE {' AND '.join(filters)}
              AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :min_score
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        async with self._session_factory() as session:
            rows = (await session.execute(sql, params)).all()
            indexed_repositories = (
                await session.scalar(
                    text("SELECT count(DISTINCT repository_id) FROM code_chunks")
                )
                or 0
            )
            last_indexed = await session.scalar(
                text("SELECT max(indexed_at) FROM code_chunks")
            )
            last_repository_change = await session.scalar(
                text(
                    "SELECT max(updated_at) FROM repositories WHERE tracked = true"
                )
            )

        results = [
            CodeSearchResult(
                repository_id=row.repository_id,
                repository_name=row.alias
                or Path(row.repository_path).name
                or row.repository_path,
                path=row.path,
                start_line=row.start_line,
                end_line=row.end_line,
                language=row.language,
                snippet=_mask_snippet(row.content[:MAX_SNIPPET_CHARS]),
                score=round(float(row.score), 4),
                url=_github_url(row.github_full_name, row.path, row.start_line),
            )
            for row in rows
        ]
        stale = _is_stale(last_indexed, last_repository_change)
        return CodeSearchResponse(
            query=query,
            model=self._settings.embedding_model,
            took_ms=round((time.perf_counter() - started) * 1000, 1),
            indexed_repositories=int(indexed_repositories),
            stale=stale,
            results=results,
        )

    async def status(self) -> CodeIndexStatus:
        self._require_postgres()
        async with self._session_factory() as session:
            indexed_repositories = (
                await session.scalar(
                    text("SELECT count(DISTINCT repository_id) FROM code_chunks")
                )
                or 0
            )
            chunks = (
                await session.scalar(text("SELECT count(*) FROM code_chunks")) or 0
            )
            last_indexed = await session.scalar(
                text("SELECT max(indexed_at) FROM code_chunks")
            )
        return CodeIndexStatus(
            indexed_repositories=int(indexed_repositories),
            indexed_chunks=int(chunks),
            last_indexed_at=last_indexed or self._last_indexed_at,
            running=self._running,
            errors=list(self._errors),
        )

    async def _index_repository(
        self,
        session: AsyncSession,
        repository: Repository,
        *,
        force: bool,
    ) -> int:
        root = Path(repository.path)
        if not root.is_dir():
            raise RagUnavailableError("repository_unavailable", "path is not a directory")
        inserted = 0
        for file_path in _iter_files(root):
            relative = file_path.relative_to(root).as_posix()
            content = _read_text(
                file_path,
                max_bytes=self._settings.rag_max_file_bytes,
            )
            if content is None:
                continue
            language = _language_for_path(file_path)
            chunks = _chunk_text(
                content,
                path=relative,
                language=language,
                max_chars=self._settings.rag_chunk_chars,
                overlap=self._settings.rag_chunk_overlap,
            )
            if not chunks:
                continue
            if not force and await self._is_unchanged(
                session, repository.id, relative, chunks
            ):
                continue
            if inserted + len(chunks) > self._settings.rag_max_chunks_per_repo:
                logger.warning(
                    "rag_chunk_limit_reached",
                    repository_id=repository.id,
                    limit=self._settings.rag_max_chunks_per_repo,
                )
                break
            await session.execute(
                text(
                    "DELETE FROM code_chunks "
                    "WHERE repository_id = :repository_id AND path = :path"
                ),
                {"repository_id": repository.id, "path": relative},
            )
            vectors = await self._embed([chunk.content for chunk in chunks])
            await self._insert_chunks(session, repository.id, chunks, vectors)
            inserted += len(chunks)
        return inserted

    async def _is_unchanged(
        self,
        session: AsyncSession,
        repository_id: int,
        path: str,
        chunks: list[_Chunk],
    ) -> bool:
        existing = set(
            (
                await session.scalars(
                    text(
                        "SELECT content_hash FROM code_chunks "
                        "WHERE repository_id = :repository_id AND path = :path"
                    ),
                    {"repository_id": repository_id, "path": path},
                )
            ).all()
        )
        return bool(existing) and existing == {chunk.content_hash for chunk in chunks}

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        batch_size = max(self._settings.embedding_batch_size, 1)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            result = await self._llm.embed(batch)
            if result is None:
                raise RagUnavailableError(
                    "embedding_unavailable",
                    "embedding model is unavailable",
                )
            for vector in result:
                if len(vector) != self._settings.embedding_dimensions:
                    raise RagUnavailableError(
                        "embedding_dimension_mismatch",
                        "embedding dimension does not match the pgvector column",
                    )
            vectors.extend(result)
        return vectors

    async def _insert_chunks(
        self,
        session: AsyncSession,
        repository_id: int,
        chunks: list[_Chunk],
        vectors: list[list[float]],
    ) -> None:
        statement = text(
            """
            INSERT INTO code_chunks
                (repository_id, path, chunk_index, start_line, end_line,
                 language, content, content_hash, embedding, embedding_model,
                 indexed_at)
            VALUES
                (:repository_id, :path, :chunk_index, :start_line, :end_line,
                 :language, :content, :content_hash,
                 CAST(:embedding AS vector), :embedding_model, :indexed_at)
            """
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            await session.execute(
                statement,
                {
                    "repository_id": repository_id,
                    "path": chunk.path,
                    "chunk_index": index,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "language": chunk.language,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "embedding": json.dumps(vector),
                    "embedding_model": self._settings.embedding_model,
                    "indexed_at": utcnow(),
                },
            )

    def _require_postgres(self) -> None:
        if not self.available:
            raise RagUnavailableError()


def _iter_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in IGNORED_DIRS and not name.startswith(".")
        ]
        for name in filenames:
            lower = name.lower()
            if lower in IGNORED_FILES or lower.startswith(".env"):
                continue
            if lower.startswith(("id_rsa", "id_ed25519")) or lower.endswith(
                (".pem", ".key", ".p12", ".pfx")
            ):
                continue
            path = Path(dirpath) / name
            if path.suffix.lower() not in ALLOWED_EXTENSIONS and not name.upper().startswith(
                "README"
            ):
                continue
            yield path


def _read_text(path: Path, *, max_bytes: int) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw:
        return None
    return raw.decode("utf-8", errors="ignore")


def _language_for_path(path: Path) -> str:
    if path.name.upper().startswith("README"):
        return "markdown"
    return ALLOWED_EXTENSIONS.get(path.suffix.lower(), "text")


def _chunk_text(
    content: str,
    *,
    path: str,
    language: str,
    max_chars: int,
    overlap: int,
) -> list[_Chunk]:
    lines = content.splitlines()
    if not lines:
        return []
    max_chars = max(max_chars, 200)
    overlap = max(min(overlap, max_chars // 2), 0)
    chunks: list[_Chunk] = []
    start = 0
    while start < len(lines):
        end = start
        size = 0
        while end < len(lines):
            line_size = len(lines[end]) + 1
            if end > start and size + line_size > max_chars:
                break
            size += line_size
            end += 1
        text_content = "\n".join(lines[start:end]).strip()
        if text_content:
            chunks.append(
                _Chunk(
                    path=path,
                    start_line=start + 1,
                    end_line=end,
                    language=language,
                    content=text_content,
                    content_hash=hashlib.sha256(
                        text_content.encode("utf-8")
                    ).hexdigest(),
                )
            )
        if end >= len(lines):
            break
        next_start = end
        overlap_size = 0
        while next_start > start and overlap_size < overlap:
            next_start -= 1
            overlap_size += len(lines[next_start]) + 1
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return chunks


def _mask_snippet(value: str) -> str:
    return SECRET_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{match.group(3)}****",
        value,
    )[:MAX_SNIPPET_CHARS]


def _github_url(
    full_name: str | None,
    path: str,
    start_line: int,
) -> str | None:
    if not full_name:
        return None
    return (
        f"https://github.com/{full_name}/blob/HEAD/{quote(path)}"
        f"#L{start_line}"
    )


def _is_stale(
    last_indexed: datetime | None,
    last_repository_change: datetime | None,
) -> bool:
    if last_indexed is None:
        return True
    if last_repository_change is None:
        return False
    return last_repository_change > last_indexed


__all__ = [
    "ALLOWED_EXTENSIONS",
    "IGNORED_DIRS",
    "CodeSearchService",
    "RagBusyError",
    "RagUnavailableError",
]
