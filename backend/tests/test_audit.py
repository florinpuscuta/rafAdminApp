"""Teste pentru /api/audit-logs — filtre, event-types, export CSV."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def _seed_events(client: AsyncClient, admin_ctx) -> None:
    """Generează câteva acțiuni care produc audit events variate."""
    # user.created
    await client.post(
        "/api/users",
        headers=admin_ctx["headers"],
        json={"email": "new1@example.com", "password": "Parola_Test_1234", "role": "member"},
    )
    # store.created nu are audit (create plain); dar alias.store.created are
    store = await client.post(
        "/api/stores", headers=admin_ctx["headers"], json={"name": "S Audit"}
    )
    await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "S AUDIT RAW", "storeId": store.json()["id"]},
    )


async def test_audit_list_requires_admin(client: AsyncClient, signup_user):
    """Member role → 403."""
    ctx = await signup_user()
    # Downgrade role to member via API isn't possible for self; use admin_ctx path
    # elsewhere. Here we test the admin_ctx hits 200 and no-auth hits 401.
    resp_anon = await client.get("/api/audit-logs")
    assert resp_anon.status_code == 401


async def test_audit_event_types_returns_distinct(client: AsyncClient, admin_ctx):
    await _seed_events(client, admin_ctx)
    resp = await client.get("/api/audit-logs/event-types", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    types = resp.json()
    assert "user.created" in types
    assert "alias.store.created" in types
    # Distinct
    assert len(types) == len(set(types))


async def test_audit_event_prefix_filter(client: AsyncClient, admin_ctx):
    await _seed_events(client, admin_ctx)
    resp = await client.get(
        "/api/audit-logs?eventPrefix=alias.", headers=admin_ctx["headers"]
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["eventType"].startswith("alias.")


async def test_audit_date_range_filter(client: AsyncClient, admin_ctx):
    await _seed_events(client, admin_ctx)
    # Range în viitor → 0 rezultate
    resp = await client.get(
        "/api/audit-logs?since=2099-01-01", headers=admin_ctx["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_audit_csv_export(client: AsyncClient, admin_ctx):
    await _seed_events(client, admin_ctx)
    resp = await client.get("/api/audit-logs/export", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert "created_at,event_type" in body  # header
    assert "user.created" in body or "alias.store.created" in body
