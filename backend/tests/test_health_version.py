"""Teste pentru /api/health și /api/version."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_health_returns_all_components(client: AsyncClient):
    resp = await client.get("/api/health")
    # 200 sau 503 — depinde dacă MinIO rulează în contextul testelor.
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "components" in body
    assert "db" in body["components"]
    assert body["components"]["db"]["status"] == "ok"
    # Celelalte componente trebuie să fie prezente (status variază)
    assert "storage" in body["components"]
    assert "email" in body["components"]
    assert "sentry" in body["components"]


async def test_health_no_auth_required(client: AsyncClient):
    """Health e PUBLIC — altfel uptime monitorii externi nu-l pot lovi."""
    # Nici un token în headers — client fixture oricum nu-l setează pentru acest path
    resp = await client.get("/api/health", headers={"Authorization": ""})
    assert resp.status_code in (200, 503)


async def test_version_returns_fields(client: AsyncClient):
    resp = await client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert "gitSha" in body
    assert "buildTime" in body
    assert "env" in body
    assert "startedAt" in body
    assert isinstance(body["uptimeSeconds"], int)
    assert body["uptimeSeconds"] >= 0


async def test_version_no_auth_required(client: AsyncClient):
    resp = await client.get("/api/version")
    assert resp.status_code == 200
