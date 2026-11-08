"""Repository identity helpers: remote URL normalisation and duplicates."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.git.command_backend import run_git
from app.models.entities import Repository

CONCURRENCY = 8
REMOTE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True, slots=True)
class RemoteRepository:
    id: int
    path: str
    name: str


@dataclass(frozen=True, slots=True)
class RemoteDuplicateGroup:
    remote_url: str
    repositories: tuple[RemoteRepository, ...]


class IdentityService:
    """Find repositories that point at the same remote URL."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        concurrency: int = CONCURRENCY,
    ) -> None:
        self._session_factory = session_factory
        self._concurrency = max(concurrency, 1)

    async def find_remote_duplicates(self) -> list[RemoteDuplicateGroup]:
        async with self._session_factory() as session:
            repositories = list(
                (await session.scalars(select(Repository).order_by(Repository.path))).all()
            )

        semaphore = asyncio.Semaphore(self._concurrency)

        async def resolve(repository: Repository) -> tuple[Repository, str | None]:
            async with semaphore:
                remote = await asyncio.to_thread(_read_remote_url, repository)
            return repository, remote

        resolved = await asyncio.gather(*(resolve(repository) for repository in repositories))
        groups: dict[str, list[RemoteRepository]] = defaultdict(list)
        for repository, remote in resolved:
            if remote is None:
                continue
            groups[remote].append(
                RemoteRepository(
                    id=repository.id,
                    path=repository.path,
                    name=repository.alias or Path(repository.path).name,
                )
            )

        result = [
            RemoteDuplicateGroup(remote_url=remote, repositories=tuple(items))
            for remote, items in groups.items()
            if len(items) > 1
        ]
        result.sort(key=lambda group: group.remote_url)
        return result


def normalize_remote_url(value: str | None) -> str | None:
    """Return ``host/owner/repo`` in lower case, or ``None`` for local paths."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None

    if raw.startswith("git@") and ":" in raw:
        host, path = raw[4:].split(":", 1)
        return _normalize_parts(host, path)

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https", "ssh", "git"} and parsed.hostname:
        return _normalize_parts(parsed.hostname, parsed.path)

    if "://" not in raw and ":" in raw and not raw.startswith(("/", "./", "../")):
        host, path = raw.split(":", 1)
        if "." in host:
            return _normalize_parts(host, path)
    return None


def _normalize_parts(host: str, path: str) -> str | None:
    cleaned_host = host.strip().lower()
    cleaned_path = path.strip().strip("/")
    if cleaned_path.endswith(".git"):
        cleaned_path = cleaned_path[:-4]
    cleaned_path = cleaned_path.rstrip("/")
    if not cleaned_host or not cleaned_path:
        return None
    return f"{cleaned_host}/{cleaned_path.lower()}"


def _read_remote_url(repository: Repository) -> str | None:
    result = run_git(
        ["config", "--get", "remote.origin.url"],
        cwd=repository.path,
        timeout=REMOTE_TIMEOUT_SECONDS,
    )
    if result.ok and result.stdout.strip():
        return normalize_remote_url(result.stdout.strip())
    if repository.github_full_name:
        return normalize_remote_url(
            f"https://github.com/{repository.github_full_name}.git"
        )
    if repository.gitflic_full_name:
        return normalize_remote_url(
            f"https://gitflic.ru/project/{repository.gitflic_full_name}.git"
        )
    return None


__all__ = [
    "IdentityService",
    "RemoteDuplicateGroup",
    "RemoteRepository",
    "normalize_remote_url",
]
