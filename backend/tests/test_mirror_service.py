"""Mirror classification and service tests (S9-011)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.models.entities import Repository, RepositoryMirrorStatus
from app.providers.base import BranchResult
from app.services.mirror_service import MirrorService, classify_mirror_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

D1 = datetime(2026, 1, 1, tzinfo=UTC)
D2 = D1 + timedelta(days=1)


class FakeClient:
    def __init__(
        self,
        branches: dict[str, BranchResult] | None = None,
        repos: list[dict[str, object]] | None = None,
        *,
        configured: bool = True,
    ) -> None:
        self.branches = branches or {}
        self.repos = repos or []
        self.configured = configured

    async def get_branch(self, full_name: str, branch: str) -> BranchResult:
        return self.branches.get(full_name, BranchResult(sha=None, found=False))

    async def list_repos(self) -> list[dict[str, object]]:
        return self.repos


def _branch(sha: str | None, date: datetime | None = D1) -> BranchResult:
    return BranchResult(sha=sha, date=date)


def test_classify_in_sync() -> None:
    status = classify_mirror_status(
        _branch("abc"), _branch("abc"), canonical_provider="github", mirror_expected=True
    )
    assert status == "in_sync"


def test_classify_missing_on_gitflic() -> None:
    status = classify_mirror_status(
        _branch("abc"), None, canonical_provider="github", mirror_expected=True
    )
    assert status == "missing_on_gitflic"


def test_classify_missing_on_github() -> None:
    status = classify_mirror_status(
        None, _branch("abc"), canonical_provider="github", mirror_expected=True
    )
    assert status == "missing_on_github"


def test_classify_behind_gitflic() -> None:
    status = classify_mirror_status(
        _branch("new", D2),
        _branch("old", D1),
        canonical_provider="github",
        mirror_expected=True,
    )
    assert status == "behind_gitflic"


def test_classify_behind_github() -> None:
    status = classify_mirror_status(
        _branch("old", D1),
        _branch("new", D2),
        canonical_provider="gitflic",
        mirror_expected=True,
    )
    assert status == "behind_github"


def test_classify_diverged() -> None:
    status = classify_mirror_status(
        _branch("aaa", D1),
        _branch("bbb", D1),
        canonical_provider="github",
        mirror_expected=True,
    )
    assert status == "diverged"


def test_classify_history_rewritten() -> None:
    status = classify_mirror_status(
        _branch("aaa", D1),
        _branch("bbb", D2),
        canonical_provider="github",
        mirror_expected=True,
    )
    assert status == "history_rewritten"


def test_classify_not_applicable() -> None:
    status = classify_mirror_status(
        _branch("aaa"), _branch("bbb"), canonical_provider="github", mirror_expected=False
    )
    assert status == "not_applicable"


def test_classify_unavailable() -> None:
    status = classify_mirror_status(
        BranchResult(error="rate_limited"),
        _branch("bbb"),
        canonical_provider="github",
        mirror_expected=True,
    )
    assert status == "unavailable"


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    *,
    github_full_name: str | None = "acme/app",
    gitflic_full_name: str | None = "acme/app",
) -> Repository:
    async with session_factory() as session:
        repository = Repository(
            path=str((tmp_path / "repo").resolve()),
            tracked=True,
            github_full_name=github_full_name,
            gitflic_full_name=gitflic_full_name,
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        session.expunge(repository)
        return repository


async def test_refresh_persists_mirror_row(session_factory, tmp_path: Path) -> None:
    repository = await _create_repository(session_factory, tmp_path)
    service = MirrorService(
        session_factory,
        FakeClient({"acme/app": _branch("sha1", D2)}),  # type: ignore[arg-type]
        FakeClient({"acme/app": _branch("sha1", D2)}),  # type: ignore[arg-type]
    )

    snapshot = await service.refresh_mirror_status(repository)
    assert snapshot.mirror_status == "in_sync"

    async with session_factory() as session:
        rows = (await session.scalars(select(RepositoryMirrorStatus))).all()
    assert len(rows) == 1
    assert rows[0].mirror_status == "in_sync"
    assert rows[0].github_head_sha == "sha1"
    assert rows[0].gitflic_head_sha == "sha1"

    await service.refresh_mirror_status(repository)
    async with session_factory() as session:
        rows = (await session.scalars(select(RepositoryMirrorStatus))).all()
    assert len(rows) == 1


async def test_discover_candidates(session_factory, tmp_path: Path) -> None:
    service = MirrorService(
        session_factory,
        FakeClient(
            repos=[
                {"provider": "github", "full_name": "acme/only-github", "private": True},
                {"provider": "github", "full_name": "acme/both", "private": True},
            ]
        ),  # type: ignore[arg-type]
        FakeClient(
            repos=[
                {"provider": "gitflic", "full_name": "acme/only-gitflic", "private": True},
                {"provider": "gitflic", "full_name": "acme/both", "private": True},
            ]
        ),  # type: ignore[arg-type]
    )

    candidates = await service.discover_candidates()

    assert [item["full_name"] for item in candidates["github_only"]] == ["acme/only-github"]
    assert [item["full_name"] for item in candidates["gitflic_only"]] == ["acme/only-gitflic"]
    assert len(candidates["both"]) == 1
    assert candidates["unknown"] == []


async def test_discover_candidates_unknown_when_unconfigured(
    session_factory, tmp_path: Path
) -> None:
    service = MirrorService(
        session_factory,
        FakeClient(configured=False),  # type: ignore[arg-type]
        FakeClient(configured=False),  # type: ignore[arg-type]
    )

    candidates = await service.discover_candidates()

    assert {item["provider"] for item in candidates["unknown"]} == {"github", "gitflic"}
