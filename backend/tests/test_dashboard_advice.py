"""AI dashboard digest tests (S38-001)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.entities import AICache, Repository, RepositoryStatus
from app.services.ai_cache import build_cache_key
from app.services.dashboard_advice_service import DashboardAdviceService
from app.services.llm_service import LLMConfig
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class FakeLLM:
    enabled = True
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, int], dict[str, object], str]] = []

    def remote_allowed(self) -> bool:
        return True

    async def resolve(self) -> LLMConfig:
        return LLMConfig(
            enabled=self.enabled,
            provider="fake",
            base_url="http://127.0.0.1:1234/v1",
            model=self.model,
            api_key="",
            timeout=30.0,
            allow_remote=True,
        )

    def allows_remote(self, config: LLMConfig) -> bool:
        return True

    async def generate_dashboard_advice(
        self,
        stats: dict[str, int],
        details: dict[str, object] | None = None,
        *,
        language: str = "ru",
    ) -> str | None:
        self.calls.append((stats, details or {}, language))
        return "Сначала закоммитьте изменения, затем обновите зависимости."


class FakeDeps:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(summary=SimpleNamespace(outdated=2))


class FakeSecurity:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(
            ecosystems=[
                SimpleNamespace(
                    vulnerabilities=[
                        SimpleNamespace(
                            cve_ids=["CVE-2023-1234"],
                            osv_id="GHSA-0001",
                            package="axios",
                            severity="critical",
                        ),
                        SimpleNamespace(
                            cve_ids=[],
                            osv_id="GHSA-0002",
                            package="lodash",
                            severity="high",
                        ),
                    ]
                )
            ]
        )


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    llm: FakeLLM,
) -> DashboardAdviceService:
    return DashboardAdviceService(
        session_factory,
        FakeDeps(),  # type: ignore[arg-type]
        FakeSecurity(),  # type: ignore[arg-type]
        llm,  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_dashboard_advice_is_cached(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = _service(session_factory, llm)

    stats = {"repositories": 2, "dirty": 1, "outdated_packages": 2}
    details: dict[str, object] = {
        "repos_with_ahead": ["app (2 коммита)"],
        "repos_with_most_outdated": [{"name": "app", "count": 2}],
        "critical_cves": [],
        "repos_dirty": ["app"],
        "repos_behind": [],
        "repos_diverged": [],
    }

    async def fake_context(language: str = "ru") -> tuple[dict[str, int], dict[str, object]]:
        return stats, details

    monkeypatch.setattr(service, "_collect_context", fake_context)

    first = await service.get_advice("ru")
    assert first.cached is False
    assert first.stats["dirty"] == 1
    assert llm.calls == [(stats, details, "ru")]

    async with session_factory() as session:
        key = build_cache_key(
            "dashboard-advice",
            "ru",
            {"stats": stats, "details": details},
            "fake-model",
            "v2",
        )
        row = await session.get(AICache, key)
        assert row is not None
        assert row.payload["advice"] == first.advice

    second = await service.get_advice("ru")
    assert second.cached is True
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_dashboard_advice_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service(session_factory, FakeLLM())

    async def fake_context(
        language: str = "ru",
    ) -> tuple[dict[str, int], dict[str, object]]:
        return {"repositories": 1, "diverged": 1}, {
            "repos_with_ahead": [],
            "repos_with_most_outdated": [],
            "critical_cves": [],
            "repos_dirty": [],
            "repos_behind": [],
            "repos_diverged": ["app"],
        }

    monkeypatch.setattr(service, "_collect_context", fake_context)
    app.state.dashboard_advice_service = service

    response = await client.post(
        "/api/v1/ai/dashboard-advice",
        json={"language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["cached"] is False
    assert payload["stats"]["diverged"] == 1

    cached = await client.post(
        "/api/v1/ai/dashboard-advice",
        json={"language": "en"},
    )
    assert cached.status_code == 200
    assert cached.json()["cached"] is True


@pytest.mark.asyncio
async def test_collect_context_names_projects_and_details(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
    make_repo: Callable[[Path], Path],
) -> None:
    dirty_path = make_repo(tmp_path / "dirty-repo")
    ahead_path = make_repo(tmp_path / "ahead-repo")

    async with session_factory() as session:
        dirty_repo = Repository(
            path=str(dirty_path.resolve()),
            alias="ai-dzenwriter",
            tracked=True,
        )
        ahead_repo = Repository(path=str(ahead_path.resolve()), tracked=True)
        session.add_all([dirty_repo, ahead_repo])
        await session.flush()
        session.add_all(
            [
                RepositoryStatus(repository_id=dirty_repo.id, state="dirty"),
                RepositoryStatus(
                    repository_id=ahead_repo.id,
                    state="ahead",
                    ahead=4,
                ),
            ]
        )
        await session.commit()

    service = _service(session_factory, FakeLLM())
    stats, details = await service._collect_context("ru")

    assert stats["repositories"] == 2
    assert stats["dirty"] == 1
    assert stats["outdated_packages"] == 4
    assert stats["high_critical_cves"] == 4
    assert details["repos_dirty"] == ["ai-dzenwriter"]
    assert details["repos_with_ahead"] == ["ahead-repo (4 коммита)"]
    assert details["repos_with_most_outdated"] == [
        {"name": "ahead-repo", "count": 2},
        {"name": "ai-dzenwriter", "count": 2},
    ]
    assert "CVE-2023-1234 в axios (проект ai-dzenwriter)" in details["critical_cves"]

