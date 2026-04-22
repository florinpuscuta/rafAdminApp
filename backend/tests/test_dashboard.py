"""Teste pentru modulul dashboard:
- overview empty (zero-safe)
- overview cu date (KPIs + top chains + top products + monthly + YoY compare)
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_overview_empty_zero_safe(client: AsyncClient, admin_ctx):
    """Fără date importate, răspunsul trebuie să fie valid, nu 500."""
    resp = await client.get(
        "/api/dashboard/overview", headers=admin_ctx["headers"]
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] is None
    assert data["availableYears"] == []
    kpis = data["kpis"]
    assert kpis["totalRows"] == 0
    assert Decimal(str(kpis["totalAmount"])) == Decimal(0)
    assert kpis["distinctMappedStores"] == 0
    assert kpis["distinctMappedAgents"] == 0
    assert data["topStores"] == []
    assert data["topAgents"] == []
    assert data["topChains"] == []
    assert data["topProducts"] == []
    assert data["monthlyTotals"] == []
    assert data["compareKpis"] is None


async def _seed_sales(client: AsyncClient, admin_ctx):
    """Setup partajat: 2 ani, mai mulți clienți/produse, alias-uri create."""
    # Canonice:
    dedeman = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Dedeman Central", "chain": "Dedeman"},
    )
    dedeman_id = dedeman.json()["id"]
    leroy = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Leroy Vest", "chain": "Leroy Merlin"},
    )
    leroy_id = leroy.json()["id"]

    await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "DEDEMAN SRL", "storeId": dedeman_id},
    )
    await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "LEROY RO", "storeId": leroy_id},
    )

    # produse canonice
    p_adeziv = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "ADE-1", "name": "Adeziv Premium"},
    )
    p_adeziv_id = p_adeziv.json()["id"]
    await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "SKU-001", "productId": p_adeziv_id},
    )

    # import pe 2026 (an curent) + 2025 (pentru YoY compare)
    rows_now = [
        sample_row(year=2026, month=1, client="DEDEMAN SRL", product_code="SKU-001", amount=1000),
        sample_row(year=2026, month=1, client="DEDEMAN SRL", product_code="SKU-001", amount=500),
        sample_row(year=2026, month=2, client="LEROY RO", product_code="SKU-001", amount=2000),
        # rând fără alias (unmapped) → tot contează la totaluri
        sample_row(year=2026, month=3, client="NEMAPAT", product_code=None, amount=250),
    ]
    imp1 = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={
            "file": (
                "now.xlsx",
                make_xlsx(rows_now),
                "application/octet-stream",
            )
        },
    )
    assert imp1.status_code == 200

    rows_prev = [
        sample_row(year=2025, month=1, client="DEDEMAN SRL", amount=800),
        sample_row(year=2025, month=2, client="LEROY RO", amount=1200),
    ]
    imp2 = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={
            "file": (
                "prev.xlsx",
                make_xlsx(rows_prev),
                "application/octet-stream",
            )
        },
    )
    assert imp2.status_code == 200

    return {
        "dedeman_id": dedeman_id,
        "leroy_id": leroy_id,
        "product_id": p_adeziv_id,
    }


async def test_overview_with_data_returns_kpis_and_breakdowns(
    client: AsyncClient, admin_ctx
):
    ids = await _seed_sales(client, admin_ctx)

    resp = await client.get(
        "/api/dashboard/overview", headers=admin_ctx["headers"]
    )
    assert resp.status_code == 200
    data = resp.json()

    # cel mai recent an e default
    assert data["year"] == 2026
    assert set(data["availableYears"]) == {2026, 2025}

    kpis = data["kpis"]
    assert kpis["totalRows"] == 4  # 3 dedeman/leroy + 1 nemapat pt 2026
    assert Decimal(str(kpis["totalAmount"])) == Decimal("3750")
    # 2 stores mapped distinct + 1 group None = 3 (distinct include None)
    assert kpis["distinctMappedStores"] >= 2
    # 1 unmapped store row (NEMAPAT)
    assert kpis["unmappedStoreRows"] == 1

    # top chains: Dedeman (1500), Leroy Merlin (2000), Nemapate (250)
    chain_totals = {row["chain"]: Decimal(str(row["totalAmount"])) for row in data["topChains"]}
    assert chain_totals["Dedeman"] == Decimal("1500")
    assert chain_totals["Leroy Merlin"] == Decimal("2000")
    assert chain_totals["Nemapate"] == Decimal("250")

    # top products: "Adeziv Premium" cu 3500 (1000+500+2000), + "Nemapate" 250
    product_totals = {p["productName"]: Decimal(str(p["totalAmount"])) for p in data["topProducts"]}
    assert product_totals.get("Adeziv Premium") == Decimal("3500")

    # top stores: Leroy Vest primul (2000), Dedeman Central (1500), Nemapate (250)
    store_names_in_order = [s["storeName"] for s in data["topStores"]]
    assert store_names_in_order[0] == "Leroy Vest"
    assert "Dedeman Central" in store_names_in_order
    assert "Nemapate" in store_names_in_order

    # monthly totals: 12 luni, ianuarie=1500, februarie=2000, martie=250, restul 0
    monthly = {m["month"]: Decimal(str(m["totalAmount"])) for m in data["monthlyTotals"]}
    assert len(monthly) == 12
    assert monthly[1] == Decimal("1500")
    assert monthly[2] == Decimal("2000")
    assert monthly[3] == Decimal("250")
    assert monthly[4] == Decimal(0)

    # YoY compare: default = anul anterior (2025)
    assert data["compareYear"] == 2025
    assert data["compareKpis"] is not None
    compare_kpis = data["compareKpis"]
    assert compare_kpis["totalRows"] == 2
    assert Decimal(str(compare_kpis["totalAmount"])) == Decimal("2000")

    monthly_cmp = {m["month"]: Decimal(str(m["totalAmount"])) for m in data["monthlyTotalsCompare"]}
    assert monthly_cmp[1] == Decimal("800")
    assert monthly_cmp[2] == Decimal("1200")


async def test_overview_explicit_year_filter(client: AsyncClient, admin_ctx):
    await _seed_sales(client, admin_ctx)
    resp = await client.get(
        "/api/dashboard/overview?year=2025",
        headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2025
    assert data["kpis"]["totalRows"] == 2
    assert Decimal(str(data["kpis"]["totalAmount"])) == Decimal("2000")


async def test_overview_compare_year_same_as_year_is_ignored(
    client: AsyncClient, admin_ctx
):
    """Dacă compare_year == year, API-ul îl ignoră (nu are sens să comparăm cu el însuși)."""
    await _seed_sales(client, admin_ctx)
    resp = await client.get(
        "/api/dashboard/overview?year=2026&compareYear=2026",
        headers=admin_ctx["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["year"] == 2026
    assert data["compareYear"] is None
    assert data["compareKpis"] is None


async def test_overview_requires_auth(client: AsyncClient):
    resp = await client.get("/api/dashboard/overview")
    assert resp.status_code == 401


async def test_overview_tenant_isolation(client: AsyncClient, signup_user):
    """Tenant B nu vede datele tenantului A în dashboard."""
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")

    # import doar pentru A
    await client.post(
        "/api/sales/import",
        headers=a["headers"],
        files={
            "file": (
                "a.xlsx",
                make_xlsx([sample_row(amount=9999)]),
                "application/octet-stream",
            )
        },
    )

    over_b = await client.get(
        "/api/dashboard/overview", headers=b["headers"]
    )
    assert over_b.status_code == 200
    kpis_b = over_b.json()["kpis"]
    assert kpis_b["totalRows"] == 0
    assert Decimal(str(kpis_b["totalAmount"])) == Decimal(0)
