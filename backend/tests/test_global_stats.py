"""Global tech-debt dashboard tests (Sprint 63)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from app.config import Settings
from app.db.base import utcnow
from app.models.entities import Repository, RepositoryStatus
from app.schemas.dependency import (
    DependencyEcosystemReport,
    DependencyPackage,
    DependencyReport,
    DependencySummary,
)
from app.schemas.security import (
    SecurityEcosystemReport,
    SecurityReport,
    SecuritySummary,
    SecurityVulnerability,
)
from app.services.global_stats_service import GlobalStatsService
from app.services.llm_service import LLMConfig
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

SeverityVuln = tuple[str, str, list[str]]


class FakeDependencyService:
    """Deterministic dependency source with a per-repository call counter."""

    def __init__(
        self,
        outdated: dict[str, int],
        *,
        fail: set[str] | None = None,
        stale: bool = False,
        delay: float = 0,
    ) -> None:
        self.outdated = outdated
        self.fail = fail or set()
        self.stale = stale
        self.delay = delay
        self.calls: list[str] = []

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        ecosystem: str | None = None,
        refresh: bool = False,
    ) -> DependencyReport:
        self.calls.append(repo_path)
        if self.delay:
            await asyncio.sleep(self.delay)
        if repo_path in self.fail:
            raise RuntimeError("dependency source unavailable")
        count = self.outdated.get(repo_path, 0)
        packages = [
            DependencyPackage(
                name=f"pkg-{repository_id}-{index}",
                declared="1.0.0",
                current="1.0.0",
                latest="2.0.0",
                status="outdated",
                kind="exact",
            )
            for index in range(count)
        ]
        return DependencyReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            ecosystems=[
                DependencyEcosystemReport(
                    ecosystem="python",
                    manifest="requirements.txt",
                    status="ok",
                    source="stale_cache" if self.stale else "registry",
                    total=count,
                    outdated=count,
                    packages=packages,
                )
            ],
            summary=DependencySummary(total=count, outdated=count),
        )


class FakeSecurityService:
    """Deterministic OSV source returning the requested vulnerabilities."""

    def __init__(
        self,
        vulnerabilities: dict[str, list[SeverityVuln]],
        *,
        fail: set[str] | None = None,
        delay: float = 0,
    ) -> None:
        self.vulnerabilities = vulnerabilities
        self.fail = fail or set()
        self.delay = delay
        self.calls: list[str] = []

    async def get_report(
        self,
        repository_id: int,
        repo_path: str,
        *,
        refresh: bool = False,
        include_secrets: bool = True,
        min_severity: str = "high",
    ) -> SecurityReport:
        self.calls.append(repo_path)
        if self.delay:
            await asyncio.sleep(self.delay)
        if repo_path in self.fail:
            raise RuntimeError("security source unavailable")
        items = self.vulnerabilities.get(repo_path, [])
        report_items = [
            SecurityVulnerability(
                package=f"pkg-{repository_id}-{index}",
                version="1.0.0",
                version_source="exact",
                osv_id=osv_id,
                cve_ids=cve_ids,
                severity=severity,
            )
            for index, (severity, osv_id, cve_ids) in enumerate(items)
        ]
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for severity, _, _ in items:
            counts[severity] += 1
        return SecurityReport(
            repository_id=repository_id,
            checked_at=utcnow(),
            status="ok",
            summary=SecuritySummary(
                total_packages=len(items),
                packages_checked=len(items),
                vulnerable=len(items),
                **counts,
            ),
            ecosystems=[
                SecurityEcosystemReport(
                    ecosystem="python",
                    manifest="requirements.txt",
                    status="ok",
                    total_packages=len(items),
                    packages_checked=len(items),
                    vulnerabilities=report_items,
                )
            ],
        )


class FakeLLM:
    """Minimal chat-model stub used by the AI advice tests."""

    def __init__(self, *, enabled: bool = True, result: str | None = None) -> None:
        self.enabled = enabled
        self.result = result or "# Что горит\n\n1. alpha — обновить зависимости."
        self.calls: list[dict[str, object]] = []

    async def resolve(self) -> LLMConfig:
        return LLMConfig(
            enabled=self.enabled,
            provider="fake",
            base_url="http://127.0.0.1:1234/v1",
            model="fake-chat-model",
            api_key="",
            timeout=5.0,
            allow_remote=False,
        )

    def allows_remote(self, config: LLMConfig) -> bool:
        return True

    async def generate_global_stats_advice(
        self,
        stats: dict[str, object],
        *,
        language: str = "ru",
    ) -> str | None:
        self.calls.append({"stats": stats, "language": language})
        return self.result


async def _create_repository(
    session_factory: async_sessionmaker[AsyncSession],
    path: Path,
    *,
    alias: str,
    tracked: bool = True,
    state: str = "current",
    modified: int = 0,
    staged: int = 0,
    untracked: int = 0,
    conflicted: int = 0,
) -> int:
    async with session_factory() as session:
        repository = Repository(
            path=str(path.resolve()), alias=alias, tracked=tracked
        )
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        session.add(
            RepositoryStatus(
                repository_id=repository.id,
                state=state,
                branch="main",
                dirty_modified=modified,
                dirty_staged=staged,
                dirty_untracked=untracked,
                dirty_conflicted=conflicted,
            )
        )
        await session.commit()
        return repository.id


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    dependency: FakeDependencyService,
    security: FakeSecurityService,
    *,
    llm: FakeLLM | None = None,
) -> GlobalStatsService:
    return GlobalStatsService(
        session_factory,
        dependency,  # type: ignore[arg-type]
        security,  # type: ignore[arg-type]
        cache_ttl_seconds=300,
        concurrency=4,
        top_limit=5,
        llm_service=llm,  # type: ignore[arg-type]
    )


def _paths(root: Path) -> dict[str, str]:
    return {
        name: str((root / name).resolve())
        for name in ("alpha", "beta", "gamma", "delta")
    }


async def test_aggregates_tech_debt_across_tracked_repositories(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    await _create_repository(
        session_factory,
        tmp_path / "alpha",
        alias="alpha",
        state="dirty",
        modified=3,
        staged=1,
    )
    await _create_repository(
        session_factory,
        tmp_path / "beta",
        alias="beta",
        state="diverged",
    )
    await _create_repository(
        session_factory,
        tmp_path / "gamma",
        alias="gamma",
        tracked=False,
    )
    await _create_repository(
        session_factory,
        tmp_path / "delta",
        alias="delta",
    )

    dependency = FakeDependencyService(
        {
            paths["alpha"]: 2,
            paths["beta"]: 1,
            paths["gamma"]: 5,
        },
        fail={paths["delta"]},
    )
    security = FakeSecurityService(
        {
            paths["alpha"]: [
                ("critical", "OSV-1", ["CVE-2026-0001"]),
                ("high", "OSV-2", ["CVE-2026-0002"]),
                ("high", "OSV-3", ["CVE-2026-0003"]),
            ],
            paths["beta"]: [("medium", "OSV-1", ["CVE-2026-0001"])],
            paths["gamma"]: [("critical", "OSV-9", ["CVE-2026-9999"])],
        },
        fail={paths["delta"]},
    )
    service = _service(session_factory, dependency, security)

    report = await service.get_global_stats()

    assert report.scope.repositories == 4
    assert report.scope.tracked == 3
    assert report.scope.scanned == 2
    assert report.scope.skipped == 1
    assert report.summary.outdated_packages == 3
    assert report.summary.unique_outdated_packages == 3
    assert report.summary.vulnerabilities.critical == 1
    assert report.summary.vulnerabilities.high == 2
    assert report.summary.vulnerabilities.medium == 1
    assert report.summary.vulnerabilities.total == 4
    assert report.summary.vulnerabilities.unique_cves == 3
    assert report.summary.dirty_files == 4
    assert report.summary.diverged_branches == 1
    assert report.summary.iac_issues == 0

    by_name = {item.name: item for item in report.repositories}
    assert by_name["alpha"].problem_score == 26
    assert by_name["alpha"].dirty_files == 4
    assert by_name["beta"].problem_score == 8
    assert by_name["beta"].diverged is True
    assert by_name["delta"].status == "error"
    assert by_name["delta"].error == "delta: all_sources_unavailable"
    assert "gamma" not in by_name

    assert [item.name for item in report.top_problematic] == ["alpha", "beta"]
    assert report.errors == ["delta: all_sources_unavailable"]
    assert report.error == "partial_data"

    calls_before = (len(dependency.calls), len(security.calls))
    cached = await service.get_global_stats()

    assert cached.cached is True
    assert (len(dependency.calls), len(security.calls)) == calls_before

    await service.get_global_stats(refresh=True)

    assert len(dependency.calls) == calls_before[0] * 2
    assert len(security.calls) == calls_before[1] * 2


async def test_empty_scope_returns_zeroes(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    dependency = FakeDependencyService({})
    security = FakeSecurityService({})
    service = _service(session_factory, dependency, security)

    report = await service.get_global_stats()

    assert report.scope.tracked == 0
    assert report.scope.scanned == 0
    assert report.summary.outdated_packages == 0
    assert report.summary.vulnerabilities.total == 0
    assert report.summary.problem_types
    assert report.top_problematic == []
    assert report.error is None
    assert dependency.calls == []
    assert security.calls == []


async def test_stale_cache_is_reported(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    await _create_repository(session_factory, tmp_path / "alpha", alias="alpha")
    dependency = FakeDependencyService({paths["alpha"]: 1}, stale=True)
    security = FakeSecurityService({})
    service = _service(session_factory, dependency, security)

    report = await service.get_global_stats()

    assert report.repositories[0].stale is True


async def test_global_stats_is_read_only(
    session_factory: async_sessionmaker[AsyncSession],
    make_repo,
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "readonly")
    (repo / "notes.txt").write_text("local change\n", encoding="utf-8")

    def git_status() -> str:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout

    before = git_status()
    await _create_repository(session_factory, repo, alias="readonly")
    dependency = FakeDependencyService({str(repo.resolve()): 1})
    security = FakeSecurityService({})
    service = _service(session_factory, dependency, security)

    await service.get_global_stats()

    assert git_status() == before


async def test_single_flight_builds_once(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    await _create_repository(session_factory, tmp_path / "alpha", alias="alpha")
    await _create_repository(session_factory, tmp_path / "beta", alias="beta")
    dependency = FakeDependencyService(
        {paths["alpha"]: 1, paths["beta"]: 1}, delay=0.02
    )
    security = FakeSecurityService({}, delay=0.02)
    service = _service(session_factory, dependency, security)

    await asyncio.gather(
        service.get_global_stats(),
        service.get_global_stats(),
        service.get_global_stats(),
    )

    assert len(dependency.calls) == 2
    assert len(security.calls) == 2


async def test_global_stats_api_and_ai_advice(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    await _create_repository(session_factory, tmp_path / "alpha", alias="alpha")
    dependency = FakeDependencyService({paths["alpha"]: 2})
    security = FakeSecurityService(
        {paths["alpha"]: [("high", "OSV-1", ["CVE-2026-0001"])]}
    )
    llm = FakeLLM()
    service = _service(session_factory, dependency, security, llm=llm)
    app.state.global_stats_service = service

    response = await client.get("/api/v1/dashboard/global-stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["outdated_packages"] == 2
    assert payload["summary"]["vulnerabilities"]["high"] == 1
    assert payload["top_problematic"][0]["name"] == "alpha"
    assert payload["cached"] is False

    advice = await client.post(
        "/api/v1/dashboard/global-stats/ai-advice",
        json={"language": "en"},
    )

    assert advice.status_code == 200
    assert advice.headers["X-AI-Cache"] == "miss"
    body = advice.json()
    assert body["summary"].startswith("#")
    assert body["cached"] is False
    assert body["priorities"][0]["repository_id"] == payload["repositories"][0][
        "repository_id"
    ]
    assert llm.calls[0]["language"] == "en"

    cached = await client.post(
        "/api/v1/dashboard/global-stats/ai-advice",
        json={"language": "en"},
    )

    assert cached.status_code == 200
    assert cached.headers["X-AI-Cache"] == "hit"
    assert cached.json()["cached"] is True
    assert len(llm.calls) == 1


async def test_ai_advice_returns_503_when_llm_disabled(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    await _create_repository(session_factory, tmp_path / "alpha", alias="alpha")
    service = _service(
        session_factory,
        FakeDependencyService({}),
        FakeSecurityService({}),
        llm=FakeLLM(enabled=False),
    )
    app.state.global_stats_service = service

    response = await client.post("/api/v1/dashboard/global-stats/ai-advice")

    assert response.status_code == 503
    assert response.json()["detail"] == "llm_unavailable"


def test_problem_score_formula() -> None:
    from app.services.global_stats_service import problem_score

    assert problem_score(
        outdated=1,
        critical=1,
        high=1,
        medium=1,
        low=1,
        unknown=1,
        dirty_files=1,
        diverged=True,
    ) == 26


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.global_stats_cache_ttl_seconds == 300
    assert settings.global_stats_concurrency == 4
    assert settings.global_stats_top_limit == 5
