"""CVE explanation tests: LLM prompt, cache and API (S33-002)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from app.config import Settings
from app.models.entities import Repository
from app.services.llm_service import LLMService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_enabled": True,
        "llm_base_url": "http://127.0.0.1:1234/v1",
        "llm_model": "test-model",
        "llm_api_key": "",
        "llm_timeout_seconds": 5,
        "llm_max_diff_chars": 10000,
        "llm_allow_remote": False,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _chat_response(message: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": message}}]},
    )


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


async def test_explain_cve_builds_grounded_prompt() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.read())
        return _chat_response(
            "Уязвимость позволяет выполнить код. Обновите пакет."
        )

    service = LLMService(_settings(), transport=httpx.MockTransport(handler))

    explanation = await service.explain_cve(
        "CVE-2026-1234",
        "Remote code execution in example package",
    )

    assert explanation == (
        "Уязвимость позволяет выполнить код. Обновите пакет."
    )
    body = captured["body"]
    assert isinstance(body, dict)
    messages = body["messages"]
    assert isinstance(messages, list)
    user_message = messages[-1]["content"]
    assert "CVE-2026-1234" in user_message
    assert "Remote code execution" in user_message


async def test_explain_cve_returns_none_on_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    service = LLMService(_settings(), transport=httpx.MockTransport(handler))

    assert await service.explain_cve("CVE-1", "summary") is None


async def test_explain_cve_disabled_does_not_call_network() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _chat_response("explanation")

    service = LLMService(
        _settings(llm_enabled=False),
        transport=httpx.MockTransport(handler),
    )

    assert await service.explain_cve("CVE-1", "summary") is None
    assert called is False


async def test_cve_explain_api_caches_explanation(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return _chat_response("Краткое объяснение уязвимости.")

    app.state.llm_service = LLMService(
        _settings(), transport=httpx.MockTransport(handler)
    )

    first = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/cve-explain",
        json={"cve_id": "CVE-2026-1234", "summary": "RCE in example"},
    )
    second = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/cve-explain",
        json={"cve_id": "CVE-2026-1234", "summary": "RCE in example"},
    )

    assert first.status_code == 200
    assert first.json()["explanation"] == "Краткое объяснение уязвимости."
    assert first.json()["cached"] is False
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert calls == 1


async def test_cve_explain_api_llm_disabled(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)
    app.state.llm_service = LLMService(_settings(llm_enabled=False))

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/cve-explain",
        json={"cve_id": "CVE-1", "summary": "summary"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "llm_disabled"


async def test_cve_explain_api_llm_unavailable(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository_id = await _create_repository(session_factory, tmp_path)

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    app.state.llm_service = LLMService(
        _settings(), transport=httpx.MockTransport(handler)
    )

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/ai/cve-explain",
        json={"cve_id": "CVE-2", "summary": "summary"},
    )

    assert response.status_code == 503
    assert "LLM недоступна" in response.json()["detail"]


async def test_cve_explain_api_missing_repository(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/repositories/999999/ai/cve-explain",
        json={"cve_id": "CVE-1", "summary": "summary"},
    )

    assert response.status_code == 404
