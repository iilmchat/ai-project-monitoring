"""AI provider profiles API and LLMService switching tests (S39-004)."""

from __future__ import annotations

from app.services.ai_provider_service import AIProviderService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _create(
    client: AsyncClient,
    *,
    name: str,
    base_url: str = "http://127.0.0.1:1234/v1",
    model: str = "qwen2.5-coder-7b-instruct",
    embedding_model: str | None = None,
    api_key: str | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/settings/ai-providers",
        json={
            "name": name,
            "base_url": base_url,
            "model_name": model,
            "embedding_model": embedding_model,
            "api_key": api_key,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_provider_crud_masking_and_first_active(
    client: AsyncClient,
) -> None:
    first = await _create(
        client,
        name="Local LM Studio",
        api_key="sk-abcdefgh12345678",
    )
    assert first["is_active"] is True
    assert first["api_key"] == "sk-a****5678"
    assert first["embedding_model"] is None

    second = await _create(
        client,
        name="Remote provider",
        base_url="https://api.example.com/v1",
        model="deepseek-chat",
    )
    assert second["is_active"] is False

    listed = await client.get("/api/v1/settings/ai-providers")
    assert listed.status_code == 200
    items = listed.json()
    assert [item["name"] for item in items] == [
        "Local LM Studio",
        "Remote provider",
    ]
    assert "sk-abcdefgh12345678" not in listed.text


async def test_provider_activation_and_api_key_preserved(
    client: AsyncClient,
) -> None:
    first = await _create(client, name="One", api_key="sk-one-123456789")
    second = await _create(client, name="Two", api_key="sk-two-123456789")

    activated = await client.post(
        f"/api/v1/settings/ai-providers/{second['id']}/activate"
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    listed = (await client.get("/api/v1/settings/ai-providers")).json()
    active = [item for item in listed if item["is_active"]]
    assert [item["id"] for item in active] == [second["id"]]

    updated = await client.patch(
        f"/api/v1/settings/ai-providers/{second['id']}",
        json={"model_name": "new-model", "api_key": ""},
    )
    assert updated.status_code == 200
    assert updated.json()["model_name"] == "new-model"
    assert updated.json()["api_key"] == "sk-t****6789"

    deleted = await client.delete(
        f"/api/v1/settings/ai-providers/{first['id']}"
    )
    assert deleted.status_code == 204


async def test_provider_embedding_model_can_be_set_and_cleared(
    client: AsyncClient,
) -> None:
    provider = await _create(
        client,
        name="LM Studio",
        embedding_model="nomic-embed-text",
    )
    assert provider["embedding_model"] == "nomic-embed-text"

    updated = await client.patch(
        f"/api/v1/settings/ai-providers/{provider['id']}",
        json={"embedding_model": "text-embedding-nomic-embed-text-v1.5"},
    )
    assert updated.status_code == 200
    assert updated.json()["embedding_model"] == "text-embedding-nomic-embed-text-v1.5"

    cleared = await client.patch(
        f"/api/v1/settings/ai-providers/{provider['id']}",
        json={"embedding_model": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["embedding_model"] is None


async def test_llm_service_uses_active_profile_without_restart(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _create(
        client,
        name="First",
        base_url="http://127.0.0.1:1234/v1",
        model="first-model",
    )
    second = await _create(
        client,
        name="Second",
        base_url="http://127.0.0.1:11434/v1",
        model="second-model",
    )

    service = AIProviderService(session_factory)
    await service.activate(second["id"])

    config = await app.state.llm_service.resolve()
    assert config.enabled is True
    assert config.model == "second-model"
    assert config.provider == "ollama"

    await service.activate(first["id"])
    config = await app.state.llm_service.resolve()
    assert config.model == "first-model"
    assert config.provider == "lmstudio"
