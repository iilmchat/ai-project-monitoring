"""First-run onboarding settings status endpoint (S50-001)."""

from __future__ import annotations

from httpx import AsyncClient


async def test_status_is_configured_when_scan_roots_present(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings/status")

    assert response.status_code == 200
    assert response.json() == {"is_configured": True}


async def test_status_is_not_configured_after_clearing_scan_roots(
    client: AsyncClient,
) -> None:
    patched = await client.patch("/api/v1/settings", json={"scan_roots": ""})
    assert patched.status_code == 200

    response = await client.get("/api/v1/settings/status")

    assert response.status_code == 200
    assert response.json() == {"is_configured": False}


async def test_status_turns_configured_after_saving_scan_roots(
    client: AsyncClient,
) -> None:
    await client.patch("/api/v1/settings", json={"scan_roots": ""})
    status = await client.get("/api/v1/settings/status")
    assert status.json() == {"is_configured": False}

    patched = await client.patch(
        "/api/v1/settings", json={"scan_roots": "/projects,/work"}
    )
    assert patched.status_code == 200

    response = await client.get("/api/v1/settings/status")
    assert response.json() == {"is_configured": True}
