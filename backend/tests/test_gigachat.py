"""GigaChat OAuth, token refresh and masking tests (S43-002)."""

from __future__ import annotations

import time

import httpx
from app.models.entities import AIProviderProfile
from app.services.gigachat_provider import GigaChatProvider
from app.services.llm_service import LLMService
from fastapi import FastAPI
from httpx import AsyncClient


def _oauth_body(token: str, *, ttl_seconds: float = 1800) -> dict[str, object]:
    return {
        "access_token": token,
        "expires_at": int((time.time() + ttl_seconds) * 1000),
    }


def _chat_body(message: str) -> dict[str, object]:
    return {"choices": [{"message": {"content": message}}]}


def _profile(**overrides: object) -> AIProviderProfile:
    values: dict[str, object] = {
        "id": 1,
        "name": "GigaChat",
        "base_url": "https://gigachat.devices.sberbank.ru/api/v1",
        "model_name": "GigaChat",
        "provider_type": "gigachat",
        "auth_type": "oauth",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "oauth_scope": "GIGACHAT_API_PERS",
    }
    values.update(overrides)
    return AIProviderProfile(**values)  # type: ignore[arg-type]


async def test_oauth_token_is_cached(
    settings,
) -> None:
    oauth_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        assert request.url.path.endswith("/api/v2/oauth")
        assert request.headers["Authorization"].startswith("Basic ")
        assert request.headers["RqUID"]
        oauth_calls += 1
        return httpx.Response(200, json=_oauth_body("token-1"))

    provider = GigaChatProvider(
        settings,
        transport=httpx.MockTransport(handler),
    )
    profile = _profile()

    first = await provider.get_token(profile)
    second = await provider.get_token(profile)

    assert first == second == "token-1"
    assert oauth_calls == 1


async def test_expired_token_is_refreshed(settings) -> None:
    tokens = iter(["token-old", "token-new"])
    oauth_calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        oauth_calls += 1
        # Less than the default 60 s refresh margin, so it is treated as stale.
        return httpx.Response(200, json=_oauth_body(next(tokens), ttl_seconds=10))

    provider = GigaChatProvider(
        settings,
        transport=httpx.MockTransport(handler),
    )
    profile = _profile()

    assert await provider.get_token(profile) == "token-old"
    assert await provider.get_token(profile) == "token-new"
    assert oauth_calls == 2


async def test_chat_retries_once_after_401(settings) -> None:
    oauth_calls = 0
    chat_calls = 0
    auth_headers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls, chat_calls
        if request.url.path.endswith("/api/v2/oauth"):
            oauth_calls += 1
            return httpx.Response(
                200,
                json=_oauth_body(f"token-{oauth_calls}"),
            )
        chat_calls += 1
        auth_headers.append(request.headers["Authorization"])
        if chat_calls == 1:
            return httpx.Response(401, json={"message": "expired"})
        return httpx.Response(200, json=_chat_body("feat: from gigachat"))

    provider = GigaChatProvider(
        settings,
        transport=httpx.MockTransport(handler),
    )
    profile = _profile()

    body = await provider.complete(
        profile,
        {"model": "GigaChat", "messages": []},
    )

    assert body["choices"][0]["message"]["content"] == "feat: from gigachat"
    assert chat_calls == 2
    assert oauth_calls == 2
    assert auth_headers == ["Bearer token-1", "Bearer token-2"]


async def test_gigachat_auth_endpoint_creates_and_updates_profile_without_secrets(
    app: FastAPI,
    client: AsyncClient,
    settings,
) -> None:
    oauth_calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        oauth_calls += 1
        return httpx.Response(200, json=_oauth_body(f"token-{oauth_calls}"))

    provider = GigaChatProvider(
        settings,
        transport=httpx.MockTransport(handler),
        session_factory=app.state.session_factory,
    )
    app.state.gigachat_provider = provider

    payload = {
        "client_id": "client-id",
        "client_secret": "super-secret-value",
        "scope": "GIGACHAT_API_PERS",
        "model_name": "GigaChat",
        "profile_name": "GigaChat",
        "activate": True,
    }
    first = await client.post(
        "/api/v1/settings/ai-providers/gigachat/auth",
        json=payload,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "ok"
    assert body["profile_id"] > 0
    assert "super-secret-value" not in first.text
    assert "token-1" not in first.text

    listed = await client.get("/api/v1/settings/ai-providers")
    items = listed.json()
    assert len(items) == 1
    assert items[0]["provider_type"] == "gigachat"
    assert items[0]["auth_type"] == "oauth"
    assert items[0]["client_id"] == "client-id"
    assert items[0]["has_client_secret"] is True
    assert items[0]["is_active"] is True
    assert "super-secret-value" not in listed.text
    assert "token-1" not in listed.text

    payload["client_secret"] = "rotated-secret"
    second = await client.post(
        "/api/v1/settings/ai-providers/gigachat/auth",
        json=payload,
    )
    assert second.status_code == 200, second.text
    assert second.json()["profile_id"] == body["profile_id"]
    assert len((await client.get("/api/v1/settings/ai-providers")).json()) == 1


async def test_llm_service_uses_gigachat_adapter(
    app: FastAPI,
    client: AsyncClient,
    settings,
) -> None:
    chat_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/v2/oauth"):
            return httpx.Response(200, json=_oauth_body("token-1"))
        chat_auth.append(request.headers["Authorization"])
        return httpx.Response(200, json=_chat_body("feat: gigachat commit"))

    provider = GigaChatProvider(
        settings,
        transport=httpx.MockTransport(handler),
        session_factory=app.state.session_factory,
    )
    app.state.gigachat_provider = provider
    response = await client.post(
        "/api/v1/settings/ai-providers/gigachat/auth",
        json={
            "client_id": "client-id",
            "client_secret": "secret",
            "model_name": "GigaChat",
            "profile_name": "GigaChat",
            "activate": True,
        },
    )
    assert response.status_code == 200, response.text

    service = LLMService(
        app.state.settings,
        session_factory=app.state.session_factory,
        gigachat=provider,
    )
    config = await service.resolve()
    assert config.provider == "gigachat"
    assert config.provider_type == "gigachat"
    assert service.allows_remote(config) is True

    message = await service.generate_commit_message("diff --git a/x b/x")
    assert message == "feat: gigachat commit"
    assert chat_auth == ["Bearer token-1"]

