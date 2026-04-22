"""Teste pentru modulul sales: import xlsx (happy + errors per-row),
listing paginated, delete batch (cascade raw_sales), import cu alias-uri
existente → auto-resolve.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_import_happy_path(client: AsyncClient, admin_ctx):
    rows = [
        sample_row(year=2026, month=1, amount=1000),
        sample_row(year=2026, month=2, amount=2000),
    ]
    content = make_xlsx(rows)
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("ok.xlsx", content, "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []


async def test_import_rejects_non_xlsx(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("data.csv", b"year,month\n1,2", "text/csv")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_format"


async def test_import_rejects_empty_file(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("empty.xlsx", b"", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "empty_file"


async def test_import_per_row_errors(client: AsyncClient, admin_ctx):
    """Rândurile invalide sunt raportate în `errors`, cele valide inserate."""
    rows = [
        sample_row(year=2026, month=1, amount=100),
        # month out of range
        sample_row(year=2026, month=13, amount=200),
        # amount None → invalid
        sample_row(year=2026, month=2, amount=None),
        sample_row(year=2026, month=3, amount=300),
    ]
    content = make_xlsx(rows)
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("mix.xlsx", content, "application/octet-stream")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["inserted"] == 2
    assert body["skipped"] == 2
    assert len(body["errors"]) == 2


async def test_import_missing_required_columns(client: AsyncClient, admin_ctx):
    """Dacă headerul nu conține coloanele obligatorii → 0 inserted + error global."""
    content = make_xlsx(
        rows=[{"foo": 1, "bar": 2}],
        headers=["foo", "bar"],
    )
    resp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("bad.xlsx", content, "application/octet-stream")},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["code"] == "parse_error"
    assert any("obligator" in e.lower() or "header" in e.lower() for e in detail["errors"])


async def test_list_sales_paginated(client: AsyncClient, admin_ctx):
    rows = [sample_row(amount=10 + i) for i in range(5)]
    content = make_xlsx(rows)
    imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("d.xlsx", content, "application/octet-stream")},
    )
    assert imp.status_code == 200

    p1 = await client.get(
        "/api/sales?page=1&pageSize=2", headers=admin_ctx["headers"]
    )
    assert p1.status_code == 200
    b1 = p1.json()
    assert b1["total"] == 5
    assert b1["page"] == 1
    assert b1["pageSize"] == 2
    assert len(b1["items"]) == 2

    p3 = await client.get(
        "/api/sales?page=3&pageSize=2", headers=admin_ctx["headers"]
    )
    b3 = p3.json()
    assert b3["total"] == 5
    assert len(b3["items"]) == 1  # ultimul rând


async def test_delete_batch_cascades_raw_sales(
    client: AsyncClient, admin_ctx
):
    content = make_xlsx([sample_row(amount=100), sample_row(amount=200)])
    imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("a.xlsx", content, "application/octet-stream")},
    )
    assert imp.status_code == 200
    assert imp.json()["inserted"] == 2

    # listăm batch-urile ca să găsim id-ul
    batches = await client.get(
        "/api/sales/batches", headers=admin_ctx["headers"]
    )
    assert batches.status_code == 200
    assert len(batches.json()) == 1
    batch_id = batches.json()[0]["id"]

    # înainte de delete: 2 rânduri
    pre = await client.get("/api/sales", headers=admin_ctx["headers"])
    assert pre.json()["total"] == 2

    # delete
    d = await client.delete(
        f"/api/sales/batches/{batch_id}", headers=admin_ctx["headers"]
    )
    assert d.status_code == 204

    # raw_sales → zero (CASCADE)
    post = await client.get("/api/sales", headers=admin_ctx["headers"])
    assert post.json()["total"] == 0

    # batch dispărut
    batches2 = await client.get(
        "/api/sales/batches", headers=admin_ctx["headers"]
    )
    assert batches2.json() == []


async def test_delete_batch_not_found_404(client: AsyncClient, admin_ctx):
    from uuid import uuid4

    resp = await client.delete(
        f"/api/sales/batches/{uuid4()}", headers=admin_ctx["headers"]
    )
    assert resp.status_code == 404


async def test_import_with_existing_aliases_auto_resolves(
    client: AsyncClient, admin_ctx
):
    """Dacă alias-urile există ÎNAINTE de import, raw_sales-urile noi trebuie
    să fie inserate deja cu store_id/agent_id/product_id populate.
    """
    # creăm entități canonice
    store_r = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Dedeman Canonic", "chain": "Dedeman"},
    )
    store_id = store_r.json()["id"]
    await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "DEDEMAN SRL", "storeId": store_id},
    )

    agent_r = await client.post(
        "/api/agents",
        headers=admin_ctx["headers"],
        json={"fullName": "Ionut Filip"},
    )
    agent_id = agent_r.json()["id"]
    await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "I. Filip", "agentId": agent_id},
    )

    product_r = await client.post(
        "/api/products",
        headers=admin_ctx["headers"],
        json={"code": "CANON-1", "name": "Canonic"},
    )
    product_id = product_r.json()["id"]
    await client.post(
        "/api/products/aliases",
        headers=admin_ctx["headers"],
        json={"rawCode": "RAW-1", "productId": product_id},
    )

    # acum importăm — rândurile trebuie să se auto-rezolve
    rows = [
        sample_row(
            client="DEDEMAN SRL",
            agent="I. Filip",
            product_code="RAW-1",
            amount=500,
        ),
        # un rând care NU se rezolvă (client necunoscut)
        sample_row(
            client="ALT CLIENT",
            agent="Alt Agent",
            product_code="RAW-Z",
            amount=100,
        ),
    ]
    content = make_xlsx(rows)
    imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("d.xlsx", content, "application/octet-stream")},
    )
    assert imp.status_code == 200
    assert imp.json()["inserted"] == 2

    sales = await client.get("/api/sales", headers=admin_ctx["headers"])
    items = sales.json()["items"]

    resolved = [i for i in items if i["client"] == "DEDEMAN SRL"][0]
    unresolved = [i for i in items if i["client"] == "ALT CLIENT"][0]

    assert resolved["storeId"] == store_id
    assert resolved["agentId"] == agent_id
    assert resolved["productId"] == product_id
    assert unresolved["storeId"] is None
    assert unresolved["agentId"] is None
    assert unresolved["productId"] is None


async def test_sales_tenant_isolation(client: AsyncClient, signup_user):
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")

    await client.post(
        "/api/sales/import",
        headers=a["headers"],
        files={
            "file": (
                "a.xlsx",
                make_xlsx([sample_row(client="A client", amount=100)]),
                "application/octet-stream",
            )
        },
    )

    # Tenant B nu vede nimic
    sales_b = await client.get("/api/sales", headers=b["headers"])
    assert sales_b.json()["total"] == 0

    sales_a = await client.get("/api/sales", headers=a["headers"])
    assert sales_a.json()["total"] == 1


async def test_import_requires_auth(client: AsyncClient):
    content = make_xlsx([sample_row()])
    resp = await client.post(
        "/api/sales/import",
        files={"file": ("x.xlsx", content, "application/octet-stream")},
    )
    assert resp.status_code == 401
