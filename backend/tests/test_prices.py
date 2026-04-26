"""Teste pentru /api/prices/ka-vs-tt — compară preț mediu KA vs TT.

`/api/demo/seed` a fost eliminat (commit 8c75c89). Folosim un mini-seed local
care importă rânduri pe AMBELE canale (KA și retail/dist) pentru același produs,
ca să obținem un dataset minim cu produse comparabile.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def _seed_minimal(client: AsyncClient, admin_ctx) -> None:
    """Seed minim: același produs pe canale KA + retail, ca să apară în comparație."""
    rows = [
        # Pe KA — clienți distinct fizic
        sample_row(
            client="DEDEMAN PITESTI", channel="KA", product_code="SKU-001",
            product_name="Adeziv Placi", amount=1000, quantity=10,
        ),
        sample_row(
            client="LEROY MERLIN BUC", channel="KA", product_code="SKU-001",
            product_name="Adeziv Placi", amount=1500, quantity=12,
        ),
        # Pe retail/TT — același cod produs, alți clienți
        sample_row(
            client="MAGAZIN ELENA SRL", channel="retail", product_code="SKU-001",
            product_name="Adeziv Placi", amount=500, quantity=4,
        ),
        sample_row(
            client="DIST GENERAL SRL", channel="dist", product_code="SKU-001",
            product_name="Adeziv Placi", amount=800, quantity=6,
        ),
    ]
    xlsx = make_xlsx(rows)
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("seed.xlsx", xlsx, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text


async def test_ka_vs_tt_returns_summary_and_rows(client: AsyncClient, admin_ctx):
    await _seed_minimal(client, admin_ctx)
    resp = await client.get(
        "/api/prices/ka-vs-tt", headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert "rows" in body
    assert len(body["rows"]) > 0


async def test_ka_vs_tt_each_row_has_both_prices(client: AsyncClient, admin_ctx):
    """Produsele incluse în comparație trebuie să aibă vânzări pe AMBELE canale."""
    await _seed_minimal(client, admin_ctx)
    resp = await client.get("/api/prices/ka-vs-tt", headers=admin_ctx["headers"])
    for row in resp.json()["rows"]:
        assert row["kaQty"] is not None and float(row["kaQty"]) > 0
        assert row["ttQty"] is not None and float(row["ttQty"]) > 0
        assert row["kaPrice"] is not None
        assert row["ttPrice"] is not None


async def test_ka_vs_tt_filters_by_year(client: AsyncClient, admin_ctx):
    """Filtru year limitează rândurile doar la anul specificat."""
    await _seed_minimal(client, admin_ctx)
    from datetime import datetime
    current_year = datetime.now().year

    resp_all = await client.get("/api/prices/ka-vs-tt", headers=admin_ctx["headers"])
    resp_filt = await client.get(
        f"/api/prices/ka-vs-tt?year={current_year}", headers=admin_ctx["headers"],
    )
    total_all = float(resp_all.json()["summary"]["kaTotalSales"] or 0)
    total_filt = float(resp_filt.json()["summary"]["kaTotalSales"] or 0)
    assert total_filt <= total_all


async def test_ka_vs_tt_tenant_isolation(client: AsyncClient, signup_user):
    """Tenant A nu vede datele lui B."""
    a = await signup_user(tenant_name="Alpha Corp")
    await signup_user(tenant_name="Beta Corp")
    b = await signup_user(tenant_name="Beta Corp 2")  # b separat
    await _seed_minimal(client, a)

    resp_b = await client.get("/api/prices/ka-vs-tt", headers=b["headers"])
    assert resp_b.status_code == 200
    assert resp_b.json()["rows"] == []


async def test_ka_vs_tt_requires_auth(client: AsyncClient):
    resp = await client.get("/api/prices/ka-vs-tt")
    assert resp.status_code == 401


async def test_ka_vs_tt_csv_export(client: AsyncClient, admin_ctx):
    await _seed_minimal(client, admin_ctx)
    resp = await client.get(
        "/api/prices/ka-vs-tt/export", headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "description,product_code,category" in body  # header
    assert body.count("\n") >= 2
