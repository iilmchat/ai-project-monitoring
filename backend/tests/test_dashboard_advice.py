"""AI dashboard digest tests (S38-001)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.models.entities import AICache
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
        self.calls: list[tuple[dict[str, int], str]] = []

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
        *,
        language: str = "ru",
    ) -> str | None:
        self.calls.append((stats, language))
        return "Сначала закоммитьте изменения, затем обновите зависимости."


class FakeDeps:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(summary=SimpleNamespace(outdated=2))


class FakeSecurity:
    async def get_report(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(
            ecosystems=[SimpleNamespace(vulnerabilities=[object(), object()])]
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

    async def fake_stats() -> dict[str, int]:
        return {"repositories": 2, "dirty": 1, "outdated_packages": 2}

    monkeypatch.setattr(service, "_collect_stats", fake_stats)

    first = await service.get_advice("ru")
    assert first.cached is False
    assert first.stats["dirty"] == 1
    assert llm.calls == [({"repositories": 2, "dirty": 1, "outdated_packages": 2}, "ru")]

    async with session_factory() as session:
        key = build_cache_key(
            "dashboard-advice",
            "ru",
            {"repositories": 2, "dirty": 1, "outdated_packages": 2},
            "fake-model",
            "v1",
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

    async def fake_stats() -> dict[str, int]:
        return {"repositories": 1, "diverged": 1}

    monkeypatch.setattr(service, "_collect_stats", fake_stats)
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
