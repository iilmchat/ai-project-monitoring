"""Global dependency aggregation tests (S33-001)."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.entities import Repository
from app.providers.package_versions import PackageVersionResult
from app.services.dependency_service import DependencyService
from app.services.global_analytics_service import GlobalAnalyticsService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeRegistry:
    def __init__(self, versions: dict[str, str]) -> None:
        self.versions = versions
        self.calls: list[str] = []

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        self.calls.append(package)
        latest = self.versions.get(package)
        if latest is None:
            return PackageVersionResult(latest=None, status="not_found")
        return PackageVersionResult(latest=latest, status="ok")


def _write_repo(
    root: Path,
    *,
    requirements: str | None = None,
    package_json: dict[str, object] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if requirements is not None:
        (root / "requirements.txt").write_text(requirements, encoding="utf-8")
    if package_json is not None:
        (root / "package.json").write_text(
            json.dumps(package_json), encoding="utf-8"
        )
    return root


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
    *,
    alias: str,
    tracked: bool = True,
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str(path.resolve()), alias=alias, tracked=tracked
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = 50,
) -> tuple[GlobalAnalyticsService, FakeRegistry, FakeRegistry]:
    pypi = FakeRegistry({"fastapi": "0.116.0", "requests": "2.32.0"})
    npm = FakeRegistry({"react": "19.2.0", "vite": "5.4.0"})
    dependency = DependencyService(session_factory, pypi, npm)
    service = GlobalAnalyticsService(
        session_factory,
        dependency,
        cache_ttl_seconds=3600,
        limit=limit,
        concurrency=2,
    )
    return service, pypi, npm


async def test_aggregates_versions_across_tracked_repositories(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    alpha = _write_repo(
        tmp_path / "alpha",
        requirements="fastapi==0.110.0\nrequests==2.31.0\n",
        package_json={"dependencies": {"react": "^18.0.0"}},
    )
    beta = _write_repo(
        tmp_path / "beta",
        requirements="fastapi>=0.115.0\n",
        package_json={
            "dependencies": {"react": "^19.0.0"},
            "devDependencies": {"vite": "~5.0.0"},
        },
    )
    gamma = _write_repo(
        tmp_path / "gamma",
        requirements="fastapi==0.1.0\n",
    )
    await _create_repository(session_factory, alpha, alias="alpha")
    await _create_repository(session_factory, beta, alias="beta")
    await _create_repository(
        session_factory, gamma, alias="gamma", tracked=False
    )
    service, pypi, npm = _service(session_factory)

    report = await service.get_global_dependencies()

    assert report.summary.repositories == 2
    assert report.summary.packages == 4
    assert report.summary.unification_candidates == 2
    assert set(report.ecosystems) == {"python", "node"}

    python = {package.name: package for package in report.ecosystems["python"]}
    fastapi = python["fastapi"]
    assert fastapi.latest_version == "0.116.0"
    assert fastapi.versions_count == 2
    assert fastapi.projects_count == 2
    assert fastapi.unification_needed is True
    assert [
        (item.version, item.projects) for item in fastapi.distribution
    ] == [
        ("0.110.0", ["alpha"]),
        ("0.115.0", ["beta"]),
    ]
    assert python["requests"].unification_needed is False

    node = {package.name: package for package in report.ecosystems["node"]}
    assert node["react"].latest_version == "19.2.0"
    assert node["react"].unification_needed is True
    assert node["vite"].projects_count == 1
    assert all("gamma" not in item.projects for item in node["react"].distribution)

    pypi.calls.clear()
    npm.calls.clear()
    cached = await service.get_global_dependencies()

    assert cached.summary.packages == 4
    assert pypi.calls == []
    assert npm.calls == []


async def test_limit_and_sorting(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    alpha = _write_repo(
        tmp_path / "alpha-limit",
        requirements="fastapi==0.110.0\nrequests==2.31.0\n",
    )
    beta = _write_repo(
        tmp_path / "beta-limit",
        requirements="fastapi==0.115.0\n",
    )
    await _create_repository(session_factory, alpha, alias="alpha")
    await _create_repository(session_factory, beta, alias="beta")
    service, _, _ = _service(session_factory, limit=1)

    report = await service.get_global_dependencies()

    python = report.ecosystems["python"]
    assert len(python) == 1
    assert python[0].name == "fastapi"
    assert report.summary.packages == 2


async def test_global_dependencies_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    alpha = _write_repo(
        tmp_path / "api-alpha",
        requirements="fastapi==0.110.0\n",
    )
    beta = _write_repo(
        tmp_path / "api-beta",
        requirements="fastapi==0.115.0\n",
    )
    await _create_repository(session_factory, alpha, alias="alpha")
    await _create_repository(session_factory, beta, alias="beta")
    service, _, _ = _service(session_factory)
    app.state.global_analytics_service = service

    response = await client.get("/api/v1/dashboard/global-dependencies")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["ecosystems"]) == {"python", "node"}
    assert payload["summary"]["repositories"] == 2
    fastapi = payload["ecosystems"]["python"][0]
    assert fastapi["name"] == "fastapi"
    assert fastapi["unification_needed"] is True
    assert fastapi["latest_version"] == "0.116.0"
