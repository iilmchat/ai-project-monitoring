"""Automation config generation tests (v1.3.0, Sprint 59)."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.entities import Repository
from app.services.automation_service import AutomationService
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def _write(path: Path, content: str = "x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_dependabot_covers_python_node_and_dotnet(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "requirements.txt", "fastapi==0.115.6\n")
    _write(repo / "frontend" / "package.json", '{"dependencies": {}}')
    _write(repo / "src" / "App" / "App.csproj", "<Project />")

    config = AutomationService().generate(str(repo), "dependabot")

    assert config.path == ".github/dependabot.yml"
    assert config.ecosystems == ["dotnet", "node", "python"]
    assert "package-ecosystem: pip" in config.content
    assert "directory: /frontend" in config.content
    assert "package-ecosystem: nuget" in config.content
    assert "directory: /src/App" in config.content
    assert config.content_hash


def test_renovate_config_is_valid_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "requirements.txt", "fastapi==0.115.6\n")
    _write(repo / "package.json", '{"dependencies": {}}')

    config = AutomationService().generate(str(repo), "renovate")

    payload = json.loads(config.content)
    assert config.path == "renovate.json"
    assert payload["extends"] == ["config:recommended"]
    assert set(payload["enabledManagers"]) == {"npm", "pip_requirements"}
    assert config.ecosystems == ["node", "python"]


def test_automation_generation_does_not_write_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / "requirements.txt", "fastapi==0.115.6\n")
    before = {path.relative_to(repo).as_posix() for path in repo.rglob("*")}

    AutomationService().generate(str(repo), "dependabot")

    after = {path.relative_to(repo).as_posix() for path in repo.rglob("*")}
    assert after == before


def test_automation_without_manifests_returns_warning(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()

    config = AutomationService().generate(str(repo), "dependabot")

    assert config.ecosystems == []
    assert "no_manifests" in config.warnings
    assert "version: 2" in config.content


async def test_automation_api_returns_config_without_writing(
    app: FastAPI,
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "api"
    repo.mkdir()
    _write(repo / "requirements.txt", "fastapi==0.115.6\n")
    async with session_factory() as session:
        repository = Repository(path=str(repo.resolve()), tracked=True)
        session.add(repository)
        await session.commit()
        await session.refresh(repository)
        repository_id = repository.id

    response = await client.post(
        f"/api/v1/repositories/{repository_id}/automation/generate",
        json={"tool": "dependabot"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool"] == "dependabot"
    assert payload["path"] == ".github/dependabot.yml"
    assert "package-ecosystem: pip" in payload["content"]
    assert not (repo / ".github" / "dependabot.yml").exists()

    missing = await client.post(
        "/api/v1/repositories/999999/automation/generate",
        json={"tool": "renovate"},
    )
    assert missing.status_code == 404
