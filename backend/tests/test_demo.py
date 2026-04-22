"""Teste pentru /api/demo/seed + /api/demo/wipe."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_seed_happy_path(client: AsyncClient, admin_ctx):
    resp = await client.post("/api/demo/seed", headers=admin_ctx["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Valorile exacte din seed — au fost definite deterministic (Random(42))
    assert body["stores"] == 7
    assert body["agents"] == 5
    assert body["products"] == 12
    assert body["sales"] >= 40 * 12  # minim 40/lună × 12 luni
    assert body["sales"] <= 50 * 12
    assert body["assignments"] > 0


async def test_seed_populates_canonicals_visible_via_listing(client: AsyncClient, admin_ctx):
    """După seed, GET /api/stores/agents/products întoarce datele."""
    await client.post("/api/demo/seed", headers=admin_ctx["headers"])

    stores = await client.get("/api/stores", headers=admin_ctx["headers"])
    assert len(stores.json()) == 7
    names = {s["name"] for s in stores.json()}
    assert "Dedeman Bucuresti Pipera" in names

    agents = await client.get("/api/agents", headers=admin_ctx["headers"])
    assert len(agents.json()) == 5

    products = await client.get("/api/products", headers=admin_ctx["headers"])
    assert len(products.json()) == 12


async def test_seed_refuses_if_tenant_not_empty(client: AsyncClient, admin_ctx):
    """Al doilea seed consecutiv returnează 409."""
    r1 = await client.post("/api/demo/seed", headers=admin_ctx["headers"])
    assert r1.status_code == 200

    r2 = await client.post("/api/demo/seed", headers=admin_ctx["headers"])
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "tenant_not_empty"


async def test_seed_requires_admin(client: AsyncClient):
    """Fără auth → 401."""
    resp = await client.post("/api/demo/seed")
    assert resp.status_code == 401


async def test_seed_tenant_isolation(client: AsyncClient, signup_user):
    """Seed pe tenant A NU afectează tenant B."""
    a = await signup_user(tenant_name="Alpha Corp")
    b = await signup_user(tenant_name="Beta Corp")

    await client.post("/api/demo/seed", headers=a["headers"])

    # Tenant B rămâne gol
    stores_b = await client.get("/api/stores", headers=b["headers"])
    assert stores_b.json() == []


async def test_wipe_clears_all_data_keeps_users(client: AsyncClient, admin_ctx):
    """Wipe șterge vânzări + canonicals + aliases + batches. Users + tenant rămân."""
    await client.post("/api/demo/seed", headers=admin_ctx["headers"])

    resp = await client.post("/api/demo/wipe", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["stores"] == 7
    assert body["agents"] == 5
    assert body["products"] == 12
    assert body["sales"] > 0

    # Totul gol acum
    assert (await client.get("/api/stores", headers=admin_ctx["headers"])).json() == []
    assert (await client.get("/api/agents", headers=admin_ctx["headers"])).json() == []
    assert (await client.get("/api/products", headers=admin_ctx["headers"])).json() == []

    # Userul curent încă e logat / accesibil
    me = await client.get("/api/auth/me", headers=admin_ctx["headers"])
    assert me.status_code == 200


async def test_seed_after_wipe_works(client: AsyncClient, admin_ctx):
    """După wipe, se poate seed din nou (validare reset cycle complet)."""
    await client.post("/api/demo/seed", headers=admin_ctx["headers"])
    await client.post("/api/demo/wipe", headers=admin_ctx["headers"])

    r = await client.post("/api/demo/seed", headers=admin_ctx["headers"])
    assert r.status_code == 200
    assert r.json()["stores"] == 7
