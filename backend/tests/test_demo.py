"""Teste pentru /api/demo/wipe.

Endpoint-ul /api/demo/seed a fost eliminat (commit 8c75c89 — refactor:
remove seed_demo_data — no more synthetic agents). Aceste teste acopera
doar /wipe, singurul rămas. Datele sunt create manual via /api/sales/import
ca să verifice că wipe le șterge corect.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_wipe_requires_auth(client: AsyncClient):
    """Fără auth → 401."""
    resp = await client.post("/api/demo/wipe")
    assert resp.status_code == 401


async def test_wipe_clears_data_keeps_users(client: AsyncClient, admin_ctx):
    """Wipe șterge vânzări + entități canonice. Users + organizația rămân."""
    # Importăm câteva rânduri ca să avem ceva de șters.
    rows = [sample_row(client="DEDEMAN PITESTI", amount=1000)]
    xlsx = make_xlsx(rows)
    imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("seed.xlsx", xlsx, "application/octet-stream")},
    )
    assert imp.status_code == 200, imp.text

    resp = await client.post("/api/demo/wipe", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    body = resp.json()
    # Cel puțin sales-ul importat e șters; numerele exacte depind de stage-ul
    # de canonicalizare automată — nu le fixăm rigid.
    assert body["sales"] >= 1

    # Toate listările întorc liste goale.
    stores = await client.get("/api/stores", headers=admin_ctx["headers"])
    assert stores.json() == []
    agents = await client.get("/api/agents", headers=admin_ctx["headers"])
    assert agents.json() == []
    products = await client.get("/api/products", headers=admin_ctx["headers"])
    assert products.json() == []

    # Userul curent încă e funcțional.
    me = await client.get("/api/auth/me", headers=admin_ctx["headers"])
    assert me.status_code == 200


async def test_wipe_on_empty_tenant(client: AsyncClient, admin_ctx):
    """Wipe pe tenant gol nu eșuează — întoarce zero-uri."""
    resp = await client.post("/api/demo/wipe", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["sales"] == 0
    assert body["stores"] == 0
