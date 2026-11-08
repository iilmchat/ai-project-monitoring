"""AI unification advice tests (S37-002)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.models.entities import AICache
from app.schemas.global_analytics import (
    GlobalDependencyPackage,
    GlobalDependencyReport,
    GlobalDependencySummary,
    VersionDistribution,
)
from app.services.global_analytics_service import (
    GlobalAnalyticsService,
    LLMUnavailableError,
    PackageNotFoundError,
    UnificationNotNeededError,
)
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeLLM:
    enabled = True
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, list[str]]]] = []

    def remote_allowed(self) -> bool:
        return True

    async def advise_unification(
        self,
        package: str,
        versions: dict[str, list[str]],
    ) -> str | None:
        self.calls.append((package, versions))
        return "Обновитесь до 0.116.0: это последняя совместимая версия."


def _report(*, unification: bool = True) -> GlobalDependencyReport:
    return GlobalDependencyReport(
        checked_at=datetime.now(UTC),
        ecosystems={
            "python": [
                GlobalDependencyPackage(
                    name="fastapi",
                    latest_version="0.116.0",
                    distribution=[
                        VersionDistribution(version="0.115.6", projects=["alpha"]),
                        VersionDistribution(version="0.116.0", projects=["beta"]),
                    ],
                    versions_count=2,
                    projects_count=2,
                    unification_needed=unification,
                )
            ],
            "node": [],
        },
        summary=GlobalDependencySummary(
            repositories=2,
            packages=1,
            unification_candidates=1 if unification else 0,
        ),
    )


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    llm: FakeLLM,
) -> GlobalAnalyticsService:
    service = GlobalAnalyticsService(
        session_factory,
        None,  # type: ignore[arg-type]
        llm_service=llm,  # type: ignore[arg-type]
        ai_cache_ttl_seconds=3600,
    )
    return service


async def test_advice_is_generated_and_cached(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = _service(session_factory, llm)
    report = _report()

    async def fake_report(*, refresh: bool = False) -> GlobalDependencyReport:
        return report

    monkeypatch.setattr(service, "get_global_dependencies", fake_report)

    first = await service.get_ai_unification_advice("python", "fastapi")

    assert first.cached is False
    assert first.model == "fake-model"
    assert "0.116.0" in first.advice
    assert llm.calls == [
        (
            "fastapi",
            {"0.115.6": ["alpha"], "0.116.0": ["beta"]},
        )
    ]

    async with session_factory() as session:
        row = await session.get(
            AICache,
            "unification-advice:python:fastapi:fake-model",
        )
        assert row is not None
        assert row.payload["advice"] == first.advice

    second = await service.get_ai_unification_advice("python", "fastapi")

    assert second.cached is True
    assert len(llm.calls) == 1


async def test_advice_errors(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = _service(session_factory, llm)
    report = _report(unification=False)

    async def fake_report(*, refresh: bool = False) -> GlobalDependencyReport:
        return report

    monkeypatch.setattr(service, "get_global_dependencies", fake_report)

    with pytest.raises(UnificationNotNeededError):
        await service.get_ai_unification_advice("python", "fastapi")

    with pytest.raises(PackageNotFoundError):
        await service.get_ai_unification_advice("python", "missing")

    llm.enabled = False
    disabled_service = _service(session_factory, llm)

    async def fake_report_enabled(*, refresh: bool = False) -> GlobalDependencyReport:
        return _report()

    monkeypatch.setattr(
        disabled_service, "get_global_dependencies", fake_report_enabled
    )
    with pytest.raises(LLMUnavailableError):
        await disabled_service.get_ai_unification_advice("python", "fastapi")


async def test_ai_advice_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = _service(session_factory, llm)
    report = _report()

    async def fake_report(*, refresh: bool = False) -> GlobalDependencyReport:
        return report

    monkeypatch.setattr(service, "get_global_dependencies", fake_report)
    app.state.global_analytics_service = service

    response = await client.post(
        "/api/v1/dashboard/global-dependencies/ai-advice",
        json={"ecosystem": "python", "package": "fastapi"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert "0.116.0" in payload["advice"]

    cached = await client.post(
        "/api/v1/dashboard/global-dependencies/ai-advice",
        json={"ecosystem": "python", "package": "fastapi"},
    )
    assert cached.status_code == 200
    assert cached.json()["cached"] is True
