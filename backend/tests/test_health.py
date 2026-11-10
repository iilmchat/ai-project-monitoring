"""Health endpoint tests (S1-005)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health(client: AsyncClient, settings) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "1.3.0"
    assert payload["db_ok"] is True
    assert payload["scan_roots"] == settings.scan_root_paths
    assert "git_version" in payload
