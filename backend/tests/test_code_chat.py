"""Conversational RAG tests (S55-001)."""

from __future__ import annotations

import pytest
from app.config import Settings
from app.schemas.code_search import CodeSearchResponse, CodeSearchResult
from app.services.code_search_service import CodeSearchService
from app.services.llm_service import LLMConfig
from fastapi import FastAPI
from httpx import AsyncClient


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "llm_enabled": True,
        "llm_base_url": "http://127.0.0.1:1234/v1",
        "llm_model": "test-model",
        "llm_allow_remote": False,
        "embedding_model": "test-embed",
        "ai_chat_max_history": 10,
        "ai_chat_max_context_chars": 12000,
        "ai_chat_max_output_chars": 4000,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class FakeLLM:
    def __init__(self, answer: str | None = "Redis used in [1]") -> None:
        self.answer = answer
        self.prompts: list[str] = []
        self.calls = 0

    async def resolve(self) -> LLMConfig:
        return LLMConfig(
            enabled=True,
            provider="fake",
            base_url="http://127.0.0.1:1234/v1",
            model="fake-model",
            api_key="",
            timeout=30.0,
            allow_remote=True,
        )

    async def answer_with_context(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1200,
        max_chars: int = 4000,
    ) -> str | None:
        self.calls += 1
        self.prompts.append(system_prompt + "\n" + user_prompt)
        return self.answer


def _response(query: str, results: list[CodeSearchResult]) -> CodeSearchResponse:
    return CodeSearchResponse(
        query=query,
        model="test-embed",
        took_ms=1.0,
        indexed_repositories=1,
        stale=False,
        results=results,
    )


@pytest.mark.asyncio
async def test_chat_with_code_builds_sources_and_context(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = CodeSearchService(
        session_factory,
        _settings(),
        llm,  # type: ignore[arg-type]
        database_url="postgresql+asyncpg://user:pass@localhost/db",
    )
    result = CodeSearchResult(
        repository_id=1,
        repository_name="demo",
        path="src/redis.py",
        start_line=10,
        end_line=20,
        language="python",
        snippet="REDIS_URL = 'redis://localhost'",
        score=0.91,
    )

    async def fake_search(*args: object, **kwargs: object) -> CodeSearchResponse:
        return _response("where is redis", [result])

    monkeypatch.setattr(service, "search", fake_search)

    payload = await service.chat_with_code(
        "где used redis?",
        [{"role": "user", "content": "previous question"}],
    )

    assert payload["answer"] == "Redis used in [1]"
    assert payload["sources"] == ["demo/src/redis.py:10-20"]
    assert payload["citations"] == [result.model_dump()]
    assert payload["model"] == "fake-model"
    assert "previous question" in llm.prompts[0]
    assert "REDIS_URL" in llm.prompts[0]
    assert "<<<CONTEXT" in llm.prompts[0]


@pytest.mark.asyncio
async def test_chat_with_code_without_results_skips_llm(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llm = FakeLLM()
    service = CodeSearchService(
        session_factory,
        _settings(),
        llm,  # type: ignore[arg-type]
        database_url="postgresql+asyncpg://user:pass@localhost/db",
    )

    async def fake_search(*args: object, **kwargs: object) -> CodeSearchResponse:
        return _response("empty", [])

    monkeypatch.setattr(service, "search", fake_search)

    payload = await service.chat_with_code("ничего не найдено", [])

    assert "нет подходящих фрагментов" in str(payload["answer"])
    assert payload["sources"] == []
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_chat_api_requires_embedding_model_on_sqlite(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/search/chat",
        json={"query": "where is redis", "history": []},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "embedding_unavailable"
