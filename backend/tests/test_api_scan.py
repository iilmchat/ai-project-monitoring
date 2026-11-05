"""API tests for scan and repository listing (S1-003)."""

from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient


def _build_tree(make_repo, root: Path) -> None:
    make_repo(root / "one")
    make_repo(root / "nested" / "two")
    make_repo(root / "node_modules" / "ignored")


async def test_scan_flow(make_repo, app, client: AsyncClient) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    response = await client.post("/api/v1/scan", json={"roots": [str(tree)], "depth": 3})
    assert response.status_code == 202
    started = response.json()
    assert started["scan_id"] > 0
    assert started["started_at"]

    scan_id = started["scan_id"]
    status_response = await client.get(f"/api/v1/scan/{scan_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["found"] == 2
    assert status_payload["added"] == 2
    assert status_payload["errors"] == []

    latest = await client.get("/api/v1/scan/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == scan_id


async def test_scan_without_body_uses_settings(make_repo, app, client: AsyncClient) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)

    response = await client.post("/api/v1/scan")
    assert response.status_code == 202

    repositories = await client.get("/api/v1/repositories")
    assert repositories.status_code == 200
    payload = repositories.json()
    assert payload["total"] == 2
    assert all(item["tracked"] is False for item in payload["items"])


async def test_repositories_pagination(make_repo, app, client: AsyncClient) -> None:
    tree = Path(app.state.settings.scan_roots.split(",")[0])
    _build_tree(make_repo, tree)
    await client.post("/api/v1/scan", json={"roots": [str(tree)], "depth": 3})

    response = await client.get("/api/v1/repositories", params={"skip": 0, "limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 1
    assert payload["skip"] == 0
    assert payload["limit"] == 1

    tracked = await client.get("/api/v1/repositories", params={"tracked": "true"})
    assert tracked.status_code == 200
    assert tracked.json()["total"] == 0


async def test_scan_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/scan/999999")
    assert response.status_code == 404


async def test_scan_latest_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/scan/latest")
    assert response.status_code == 404
