"""Teste pentru /api/prices/ka-vs-tt — compară preț mediu KA vs TT."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def _seed_demo(client: AsyncClient, admin_ctx) -> None:
    await client.post("/api/demo/seed", headers=admin_ctx["headers"])


async def test_ka_vs_tt_returns_summary_and_rows(client: AsyncClient, admin_ctx):
    await _seed_demo(client, admin_ctx)
    resp = await client.get(
        "/api/prices/ka-vs-tt", headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert "rows" in body
    # Demo seed are channel-uri "KA", "retail", "dist" → toate produsele au vânzări pe KA și pe non-KA
    assert len(body["rows"]) > 0


async def test_ka_vs_tt_each_row_has_both_prices(client: AsyncClient, admin_ctx):
    """Produsele incluse în comparație trebuie să aibă vânzări pe AMBELE canale."""
    await _seed_demo(client, admin_ctx)
    resp = await client.get("/api/prices/ka-vs-tt", headers=admin_ctx["headers"])
    for row in resp.json()["rows"]:
        assert row["kaQty"] is not None and float(row["kaQty"]) > 0
        assert row["ttQty"] is not None and float(row["ttQty"]) > 0
        assert row["kaPrice"] is not None
        assert row["ttPrice"] is not None


async def test_ka_vs_tt_filters_by_year(client: AsyncClient, admin_ctx):
    """Filtru year limitează rândurile doar la anul specificat."""
    await _seed_demo(client, admin_ctx)
    # Demo seed distribuie pe ultimele 12 luni; filtrare pe anul curent ar trebui să returneze subset
    from datetime import datetime
    current_year = datetime.now().year

    resp_all = await client.get("/api/prices/ka-vs-tt", headers=admin_ctx["headers"])
    resp_filt = await client.get(
        f"/api/prices/ka-vs-tt?year={current_year}", headers=admin_ctx["headers"],
    )
    # Summary filtrat are ka_total_sales <= summary total
    total_all = float(resp_all.json()["summary"]["kaTotalSales"] or 0)
    total_filt = float(resp_filt.json()["summary"]["kaTotalSales"] or 0)
    assert total_filt <= total_all


async def test_ka_vs_tt_tenant_isolation(client: AsyncClient, signup_user):
    """Tenant A nu vede datele lui B."""
    a = await signup_user(tenant_name="Alpha Corp")
    b = await signup_user(tenant_name="Beta Corp")
    await client.post("/api/demo/seed", headers=a["headers"])

    resp_b = await client.get("/api/prices/ka-vs-tt", headers=b["headers"])
    assert resp_b.status_code == 200
    assert resp_b.json()["rows"] == []


async def test_ka_vs_tt_requires_auth(client: AsyncClient):
    resp = await client.get("/api/prices/ka-vs-tt")
    assert resp.status_code == 401


async def test_ka_vs_tt_csv_export(client: AsyncClient, admin_ctx):
    await _seed_demo(client, admin_ctx)
    resp = await client.get(
        "/api/prices/ka-vs-tt/export", headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    body = resp.text
    assert "description,product_code,category" in body  # header
    # Cel puțin o linie de date
    assert body.count("\n") >= 2
