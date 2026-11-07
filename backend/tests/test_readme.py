"""README and repository document tests (S35-002)."""

from __future__ import annotations

from pathlib import Path

from app.models.entities import Repository
from app.services.readme_service import (
    DocumentAccessError,
    DocumentNotFoundError,
    parse_readme_metadata,
    read_document,
    read_readme,
)
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_parse_readme_metadata_extracts_title_and_version() -> None:
    content = (
        "# IIRuchating — мониторинг проектов\n\n"
        "**Версия:** v0.7.0 · **Лицензия:** MIT\n"
    )

    name, version = parse_readme_metadata(content, fallback="fallback")

    assert name == "IIRuchating — мониторинг проектов"
    assert version == "v0.7.0"


def test_parse_readme_metadata_falls_back_without_heading() -> None:
    name, version = parse_readme_metadata("Version: 1.2.3\n", fallback="repo")

    assert name == "repo"
    assert version == "1.2.3"


def test_read_readme_finds_case_insensitive_file(tmp_path: Path) -> None:
    (tmp_path / "ReadMe.MD").write_text("# Demo\nVersion: 2.1.0\n", encoding="utf-8")

    readme = read_readme(tmp_path)

    assert readme is not None
    assert readme.path == "ReadMe.MD"
    assert readme.name == "Demo"
    assert readme.version == "2.1.0"


def test_read_document_blocks_traversal(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n", encoding="utf-8")

    document = read_document(tmp_path, "docs/SPEC.md")
    assert document.content == "# Spec\n"

    for bad in ("../outside.md", "/etc/passwd", "docs/../secret.md"):
        try:
            read_document(tmp_path, bad)
        except DocumentAccessError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError(f"path must be rejected: {bad}")

    try:
        read_document(tmp_path, "docs/missing.md")
    except DocumentNotFoundError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("missing document must raise")


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


async def test_readme_api(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text(
        "# Project X\n\n**Версия:** v1.2.3\n", encoding="utf-8"
    )
    repository_id = await _create_repository(session_factory, tmp_path)

    response = await client.get(f"/api/v1/repositories/{repository_id}/readme")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Project X"
    assert payload["version"] == "v1.2.3"
    assert payload["path"] == "README.md"


async def test_docs_api_and_traversal(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ARCHITECTURE.md").write_text("# Arch\n", encoding="utf-8")
    repository_id = await _create_repository(session_factory, tmp_path)

    response = await client.get(
        f"/api/v1/repositories/{repository_id}/docs",
        params={"path": "docs/ARCHITECTURE.md"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "# Arch\n"

    blocked = await client.get(
        f"/api/v1/repositories/{repository_id}/docs",
        params={"path": "../secret.md"},
    )
    assert blocked.status_code == 400
