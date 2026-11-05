"""Bulk migration to GitFlic tests (S15-002)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository, RepositoryMirrorStatus
from app.services.bulk_service import BulkService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _repo(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    name: str,
    *,
    canonical: str,
    gitflic_full_name: str | None,
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str((tmp_path / name).resolve()),
            tracked=True,
            canonical_provider=canonical,
            gitflic_full_name=gitflic_full_name,
            mirror_policy="github_to_gitflic",
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_migrate_to_gitflic(session_factory, tmp_path: Path) -> None:
    migrated_id = await _repo(
        session_factory, tmp_path, "migrate", canonical="github", gitflic_full_name="acme/app"
    )
    skipped_id = await _repo(
        session_factory, tmp_path, "skip", canonical="github", gitflic_full_name=None
    )
    other_id = await _repo(
        session_factory, tmp_path, "other", canonical="gitflic", gitflic_full_name="acme/other"
    )
    async with session_factory() as session:
        session.add(
            RepositoryMirrorStatus(
                repository_id=migrated_id,
                mirror_status="behind_gitflic",
                details={},
            )
        )
        await session.commit()

    summary = await BulkService(session_factory).migrate_to_gitflic()

    assert summary == {"updated": 1, "skipped": 1, "total": 2}

    async with session_factory() as session:
        migrated = await session.get(Repository, migrated_id)
        skipped = await session.get(Repository, skipped_id)
        other = await session.get(Repository, other_id)
        mirror_rows = (await session.scalars(select(RepositoryMirrorStatus))).all()

    assert migrated is not None
    assert migrated.canonical_provider == "gitflic"
    assert migrated.mirror_policy == "gitflic_to_github"
    assert skipped is not None
    assert skipped.canonical_provider == "github"
    assert other is not None
    assert other.canonical_provider == "gitflic"
    assert mirror_rows == []
