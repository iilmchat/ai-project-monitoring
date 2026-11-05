"""Dependency parser, cache and API tests (S25-001…S25-004)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.models.entities import Repository
from app.providers.pypi_client import PackageVersionResult
from app.services.dependency_parser import parse_requirements
from app.services.dependency_service import DependencyService
from app.services.node_parser import parse_package_json
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeRegistry:
    def __init__(
        self,
        versions: dict[str, str | None],
        errors: dict[str, str] | None = None,
    ) -> None:
        self.versions = versions
        self.errors = errors or {}
        self.calls: list[str] = []

    async def get_latest_version(self, package: str) -> PackageVersionResult:
        self.calls.append(package)
        error = self.errors.get(package)
        if error is not None:
            return PackageVersionResult(latest=None, status=error, error=error)
        latest = self.versions.get(package)
        if latest is None:
            return PackageVersionResult(latest=None, status="not_found")
        return PackageVersionResult(latest=latest, status="ok")


def _write_requirements(path: Path, content: str) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "requirements.txt").write_text(content, encoding="utf-8")
    return path


def test_parser_handles_pins_ranges_includes_and_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_requirements(
        repo,
        "\n".join(
            [
                "# base dependencies",
                "fastapi==0.115.6  # pinned",
                "requests>=2.31,<3",
                "uvicorn[standard]~=0.34.0",
                'pydantic==2.10.4 ; python_version >= "3.11"',
                "-r extra.txt",
                "--hash=sha256:deadbeef",
                "-e .",
                "git+https://github.com/acme/lib.git#egg=acme-lib",
                "https://example.com/pkg.whl",
            ]
        ),
    )
    (repo / "extra.txt").write_text(
        "httpx==0.28.1\n-r requirements.txt\n",
        encoding="utf-8",
    )

    result = parse_requirements(repo)

    assert result.error is None
    by_name = {package.name: package for package in result.packages}
    assert by_name["fastapi"].kind == "exact"
    assert by_name["fastapi"].current == "0.115.6"
    assert by_name["requests"].kind == "range"
    assert by_name["requests"].current == "2.31"
    assert by_name["uvicorn"].current == "0.34.0"
    assert by_name["pydantic"].current == "2.10.4"
    assert by_name["httpx"].current == "0.28.1"
    assert by_name["editable"].kind == "path"
    assert by_name["acme-lib"].kind == "vcs"
    assert by_name["pkg-whl"].kind == "path"
    assert all(package.manifest_line is not None for package in result.packages)


def test_parser_does_not_follow_include_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write_requirements(repo, "-r ../outside.txt\nfastapi==0.115.6\n")
    outside = tmp_path / "outside.txt"
    outside.write_text("evil==1.0\n", encoding="utf-8")

    result = parse_requirements(repo)

    assert [package.name for package in result.packages] == ["fastapi"]


def test_parser_missing_manifest(tmp_path: Path) -> None:
    result = parse_requirements(tmp_path)

    assert result.manifest_found is False
    assert result.packages == []


def test_node_parser_handles_sections_and_ignored_specs(tmp_path: Path) -> None:
    repo = tmp_path / "node"
    repo.mkdir()
    (repo / "package.json").write_text(
        """{
          "dependencies": {
            "react": "^19.0.0",
            "local-lib": "file:../local-lib",
            "git-lib": "git+https://github.com/acme/git-lib.git"
          },
          "devDependencies": {
            "vite": "~8.0.0",
            "workspace-lib": "workspace:*"
          },
          "optionalDependencies": {
            "optional-lib": "^1.0.0"
          }
        }""",
        encoding="utf-8",
    )

    result = parse_package_json(repo)

    assert result.error is None
    by_name = {package.name: package for package in result.packages}
    assert by_name["react"].kind == "range"
    assert by_name["react"].current == "19.0.0"
    assert by_name["react"].manifest_section == "dependencies"
    assert by_name["vite"].current == "8.0.0"
    assert by_name["vite"].manifest_section == "devDependencies"
    assert by_name["local-lib"].kind == "path"
    assert by_name["git-lib"].kind == "vcs"
    assert by_name["workspace-lib"].kind == "workspace"
    assert "optional-lib" not in by_name


async def test_service_builds_report_and_uses_cache(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(
        tmp_path / "repo",
        "fastapi==0.115.6\nrequests>=2.31\n",
    )
    registry = FakeRegistry(
        {"fastapi": "0.115.6", "requests": "2.32.0"},
    )
    service = DependencyService(session_factory, registry)

    report = await service.get_report(1, str(repo), ecosystem="python")

    ecosystem = report.ecosystems[0]
    assert ecosystem.status == "ok"
    assert ecosystem.source == "registry"
    assert ecosystem.total == 2
    assert ecosystem.outdated == 1
    assert ecosystem.up_to_date == 1
    by_name = {package.name: package for package in ecosystem.packages}
    assert by_name["fastapi"].status == "current"
    assert by_name["requests"].status == "outdated"
    assert by_name["requests"].severity == "minor"
    assert set(registry.calls) == {"fastapi", "requests"}

    registry.calls.clear()
    cached = await service.get_report(1, str(repo), ecosystem="python")

    assert cached.ecosystems[0].source == "cache"
    assert registry.calls == []

    refreshed = await service.get_report(
        1, str(repo), ecosystem="python", refresh=True
    )

    assert refreshed.ecosystems[0].source == "registry"
    assert set(registry.calls) == {"fastapi", "requests"}


async def test_service_uses_stale_cache_on_registry_error(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "fastapi==0.115.6\n")
    registry = FakeRegistry({"fastapi": "0.115.6"})
    service = DependencyService(session_factory, registry)
    await service.get_report(1, str(repo), ecosystem="python")

    registry.errors["fastapi"] = "rate_limited"
    report = await service.get_report(
        1, str(repo), ecosystem="python", refresh=True
    )

    ecosystem = report.ecosystems[0]
    assert ecosystem.source == "stale_cache"
    assert ecosystem.error == "rate_limited"
    assert ecosystem.packages[0].latest == "0.115.6"


async def test_service_without_cache_marks_registry_unavailable(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "fastapi==0.115.6\n")
    registry = FakeRegistry({}, errors={"fastapi": "rate_limited"})
    service = DependencyService(session_factory, registry)

    report = await service.get_report(1, str(repo), ecosystem="python")

    ecosystem = report.ecosystems[0]
    assert ecosystem.status == "unavailable"
    assert ecosystem.error == "rate_limited"
    assert ecosystem.packages[0].status == "unknown"


async def test_service_ttl_expiry_refetches(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "fastapi==0.115.6\n")
    registry = FakeRegistry({"fastapi": "0.115.6"})
    service = DependencyService(session_factory, registry, cache_ttl_seconds=0)

    await service.get_report(1, str(repo), ecosystem="python")
    await service.get_report(1, str(repo), ecosystem="python")

    assert registry.calls == ["fastapi", "fastapi"]


async def test_service_caches_not_found_as_unknown(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "missing-package==1.0\n")
    registry = FakeRegistry({})
    service = DependencyService(session_factory, registry)

    first = await service.get_report(1, str(repo), ecosystem="python")
    second = await service.get_report(1, str(repo), ecosystem="python")

    assert first.ecosystems[0].packages[0].status == "unknown"
    assert first.ecosystems[0].packages[0].latest is None
    assert second.ecosystems[0].source == "cache"
    assert registry.calls == ["missing-package"]


async def test_service_single_flight_for_same_package(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = _write_requirements(tmp_path / "repo", "fastapi==0.115.6\n")
    registry = FakeRegistry({"fastapi": "0.115.6"})
    service = DependencyService(session_factory, registry)

    await asyncio.gather(
        service.get_report(1, str(repo), ecosystem="python"),
        service.get_report(1, str(repo), ecosystem="python"),
    )

    assert registry.calls == ["fastapi"]


async def test_service_no_manifest_and_node_placeholder(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    service = DependencyService(session_factory, FakeRegistry({}))

    report = await service.get_report(1, str(tmp_path))

    assert [item.ecosystem for item in report.ecosystems] == ["python", "node"]
    assert report.ecosystems[0].status == "no_manifest"
    assert report.ecosystems[1].status == "no_manifest"


async def test_service_node_report_uses_npm_registry_and_cache(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "node-repo"
    repo.mkdir()
    (repo / "package.json").write_text(
        """{
          "dependencies": {"react": "^19.0.0", "local-lib": "file:../local"},
          "devDependencies": {"vite": "~8.0.0"}
        }""",
        encoding="utf-8",
    )
    pypi = FakeRegistry({})
    npm = FakeRegistry({"react": "19.2.0", "vite": "8.3.5"})
    service = DependencyService(session_factory, pypi, npm)

    report = await service.get_report(1, str(repo), ecosystem="node")

    ecosystem = report.ecosystems[0]
    assert ecosystem.ecosystem == "node"
    assert ecosystem.status == "ok"
    assert ecosystem.source == "registry"
    assert ecosystem.total == 3
    assert ecosystem.outdated == 2
    assert ecosystem.ignored == 1
    by_name = {package.name: package for package in ecosystem.packages}
    assert by_name["react"].manifest_section == "dependencies"
    assert by_name["vite"].manifest_section == "devDependencies"
    assert set(npm.calls) == {"react", "vite"}
    assert pypi.calls == []

    npm.calls.clear()
    cached = await service.get_report(1, str(repo), ecosystem="node")

    assert cached.ecosystems[0].source == "cache"
    assert npm.calls == []


async def test_service_combined_report_sums_outdated(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "combined"
    repo.mkdir()
    (repo / "requirements.txt").write_text("fastapi==0.115.6\n", encoding="utf-8")
    (repo / "package.json").write_text(
        """{"dependencies": {"react": "^19.0.0"}}""",
        encoding="utf-8",
    )
    service = DependencyService(
        session_factory,
        FakeRegistry({"fastapi": "0.116.0"}),
        FakeRegistry({"react": "19.2.0"}),
    )

    report = await service.get_report(1, str(repo), ecosystem="all")

    assert [item.ecosystem for item in report.ecosystems] == ["python", "node"]
    assert report.ecosystems[0].outdated == 1
    assert report.ecosystems[1].outdated == 1
    assert report.summary.total == 2
    assert report.summary.outdated == 2


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
) -> int:
    async with session_factory() as session:
        repository = Repository(path=str(path.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        return repository.id


async def test_dependencies_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repo = _write_requirements(
        tmp_path / "repo",
        "fastapi==0.115.6\nrequests>=2.31\n",
    )
    repository_id = await _create_repository(session_factory, repo)
    app.state.dependency_service = DependencyService(
        session_factory,
        FakeRegistry({"fastapi": "0.116.0", "requests": "2.32.0"}),
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/dependencies",
        params={"ecosystem": "python"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository_id"] == repository_id
    assert len(payload["ecosystems"]) == 1
    ecosystem = payload["ecosystems"][0]
    assert ecosystem["status"] == "ok"
    assert ecosystem["total"] == 2
    assert ecosystem["outdated"] == 2
    assert ecosystem["packages"][0]["name"] == "fastapi"
    assert ecosystem["packages"][0]["severity"] == "minor"
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["outdated"] == 2


async def test_dependencies_api_all_combines_ecosystems(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "combined-api"
    repo.mkdir()
    (repo / "requirements.txt").write_text("fastapi==0.115.6\n", encoding="utf-8")
    (repo / "package.json").write_text(
        """{"dependencies": {"react": "^19.0.0"}}""",
        encoding="utf-8",
    )
    repository_id = await _create_repository(session_factory, repo)
    app.state.dependency_service = DependencyService(
        session_factory,
        FakeRegistry({"fastapi": "0.116.0"}),
        FakeRegistry({"react": "19.2.0"}),
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/dependencies",
        params={"ecosystem": "all"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["ecosystem"] for item in payload["ecosystems"]] == ["python", "node"]
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["outdated"] == 2


async def test_dependencies_api_no_manifest(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.dependency_service = DependencyService(
        session_factory,
        FakeRegistry({}),
    )

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/dependencies",
        params={"ecosystem": "python"},
    )

    assert response.status_code == 200
    assert response.json()["ecosystems"][0]["status"] == "no_manifest"


async def test_dependencies_api_missing_repository(client: AsyncClient) -> None:
    response = await client.get("/api/v1/repositories/999999/dependencies")

    assert response.status_code == 404
