"""Discovery service tests on real temporary Git repositories (S1-004)."""

from __future__ import annotations

from pathlib import Path

from app.db.base import utcnow
from app.models.entities import Repository, ScanRun
from app.services.discovery_service import DiscoveryService
from sqlalchemy import select


def _build_tree(make_repo, root: Path) -> None:
    make_repo(root / "repo_alpha")  # level 1
    make_repo(root / "group" / "repo_beta")  # level 2
    make_repo(root / "group" / "deep" / "repo_gamma")  # level 3
    make_repo(root / "group" / "deep" / "too_deep" / "repo_delta")  # level 4
    make_repo(root / "node_modules" / "repo_ignored")  # ignored
    make_repo(root / "NODE_MODULES" / "repo_ignored_upper")  # ignored (case-insensitive)
    make_repo(root / "repo_alpha" / "vendor" / "repo_vendor")  # ignored
    make_repo(root / "repo_alpha" / "sub" / "repo_nested")  # level 3, nested repo


async def test_scan_finds_expected_repositories(make_repo, app) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    service = DiscoveryService(app.state.session_factory)
    result = await service.scan_directory([str(tree)], 3, ["node_modules", "vendor"])

    found = {Path(path).name for path in result.repositories}
    assert found == {"repo_alpha", "repo_beta", "repo_gamma", "repo_nested"}
    assert result.found_count == 4
    assert result.added_count == 4
    assert result.status == "completed"
    assert result.skipped_count >= 2


async def test_scan_respects_depth_limit(make_repo, app) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    service = DiscoveryService(app.state.session_factory)
    shallow = await service.scan_directory([str(tree)], 1, ["node_modules", "vendor"])
    shallow_names = {Path(path).name for path in shallow.repositories}
    assert shallow_names == {"repo_alpha"}

    deep = await service.scan_directory([str(tree)], 4, ["node_modules", "vendor"])
    deep_names = {Path(path).name for path in deep.repositories}
    assert "repo_delta" in deep_names


async def test_scan_persists_untracked_repositories(make_repo, app, session_factory) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    service = DiscoveryService(session_factory)
    first = await service.scan_directory([str(tree)], 3, ["node_modules", "vendor"])
    second = await service.scan_directory([str(tree)], 3, ["node_modules", "vendor"])

    assert first.added_count == 4
    assert second.added_count == 0
    assert second.found_count == 4

    async with session_factory() as session:
        repositories = (await session.scalars(select(Repository))).all()
    assert len(repositories) == 4
    assert all(repository.tracked is False for repository in repositories)


async def test_scan_updates_scan_run(make_repo, app, session_factory) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    async with session_factory() as session:
        run = ScanRun(started_at=utcnow(), status="pending", roots=[str(tree)], depth=3)
        session.add(run)
        await session.commit()
        await session.refresh(run)
        scan_run_id = run.id

    service = DiscoveryService(session_factory)
    await service.scan_directory(
        [str(tree)], 3, ["node_modules", "vendor"], scan_run_id=scan_run_id
    )

    async with session_factory() as session:
        stored = await session.get(ScanRun, scan_run_id)
    assert stored is not None
    assert stored.status == "completed"
    assert stored.found_count == 4
    assert stored.added_count == 4
    assert stored.finished_at is not None


async def test_scan_reports_missing_root(app, session_factory) -> None:
    service = DiscoveryService(session_factory)
    result = await service.scan_directory(
        [str(Path(app.state.settings.scan_roots) / "nope")], 3, []
    )
    assert result.found_count == 0
    assert result.errors
