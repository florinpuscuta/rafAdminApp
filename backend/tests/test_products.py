"""Teste pentru modulul products: create, alias + backfill."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_create_product_201(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={
            "code": "SKU-A1",
            "name": "Adeziv Placi Ceramice 25kg",
            "category": "adezivi",
            "brand": "Adeplast",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "SKU-A1"
    assert data["name"] == "Adeziv Placi Ceramice 25kg"
    assert data["category"] == "adezivi"


async def test_create_product_duplicate_code_409(client: AsyncClient, admin_ctx):
    await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "DUP", "name": "A"},
    )
    second = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "DUP", "name": "B"},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "product_exists"


async def test_alias_backfills_product_id_on_raw_sales(
    client: AsyncClient, admin_ctx
):
    rows = [
        sample_row(product_code="RAW-001", product_name="Adeziv X", amount=100),
        sample_row(product_code="RAW-001", product_name="Adeziv X", amount=200),
        sample_row(product_code="RAW-002", product_name="Altul", amount=50),
    ]
    content = make_xlsx(rows)
    r_imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("data.xlsx", content, "application/octet-stream")},
    )
    assert r_imp.status_code == 200
    assert r_imp.json()["inserted"] == 3

    unm = await client.get(
        "/api/products/unmapped", headers=admin_ctx["headers"]
    )
    assert {r["rawCode"] for r in unm.json()} == {"RAW-001", "RAW-002"}

    product = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "SKU-CANONIC", "name": "Adeziv canonic"},
    )
    product_id = product.json()["id"]

    alias = await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "RAW-001", "productId": product_id},
    )
    assert alias.status_code == 201

    unm2 = await client.get(
        "/api/products/unmapped", headers=admin_ctx["headers"]
    )
    assert {r["rawCode"] for r in unm2.json()} == {"RAW-002"}


async def test_create_alias_unknown_product_404(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "X", "productId": str(uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "product_not_found"


async def test_alias_duplicate_raw_code_409(client: AsyncClient, admin_ctx):
    product = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "SKU", "name": "name"},
    )
    pid = product.json()["id"]
    a1 = await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "raw", "productId": pid},
    )
    assert a1.status_code == 201
    a2 = await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "raw", "productId": pid},
    )
    assert a2.status_code == 409


async def test_products_tenant_isolation(client: AsyncClient, signup_user):
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")
    await client.post(
        "/api/products",
        headers=a["headers"],
        json={"code": "A-CODE", "name": "A prod"},
    )
    await client.post(
        "/api/products",
        headers=b["headers"],
        json={"code": "B-CODE", "name": "B prod"},
    )
    list_a = await client.get("/api/products", headers=a["headers"])
    codes_a = {p["code"] for p in list_a.json()}
    assert codes_a == {"A-CODE"}


async def test_merge_products_consolidates_sales_and_aliases(
    client: AsyncClient, admin_ctx
):
    from tests._helpers import make_xlsx, sample_row
    p = await client.post("/api/products", headers=admin_ctx["headers"],
                         json={"code": "SKU-A", "name": "Adeziv"})
    d = await client.post("/api/products", headers=admin_ctx["headers"],
                         json={"code": "SKU-A-DUP", "name": "Adeziv dup"})
    primary_id, dup_id = p.json()["id"], d.json()["id"]

    rows = [sample_row(product_code="RAW-CODE", amount=300)]
    await client.post("/api/sales/import", headers=admin_ctx["headers"],
                     files={"file": ("x.xlsx", make_xlsx(rows), "application/octet-stream")})
    await client.post("/api/products/aliases", headers=admin_ctx["headers"],
                     json={"rawCode": "RAW-CODE", "productId": dup_id})

    m = await client.post("/api/products/merge", headers=admin_ctx["headers"],
                         json={"primaryId": primary_id, "duplicateIds": [dup_id]})
    assert m.status_code == 200, m.text
    body = m.json()
    assert body["mergedCount"] == 1
    assert body["aliasesReassigned"] == 1
    assert body["salesReassigned"] == 1

    products = await client.get("/api/products", headers=admin_ctx["headers"])
    ids = {x["id"] for x in products.json()}
    assert dup_id not in ids
