"""Teste pentru modulul stores: create, alias + backfill raw_sales,
list unmapped, resolve_map, tenant isolation.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_create_store_201(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Dedeman Pipera", "chain": "Dedeman", "city": "Bucuresti"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Dedeman Pipera"
    assert data["chain"] == "Dedeman"
    assert data["city"] == "Bucuresti"
    assert data["active"] is True


async def test_list_stores_empty(client: AsyncClient, admin_ctx):
    resp = await client.get("/api/stores", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_stores_returns_created(client: AsyncClient, admin_ctx):
    await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Store 1"},
    )
    await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Store 2"},
    )
    resp = await client.get("/api/stores", headers=admin_ctx["headers"])
    assert resp.status_code == 200
    names = {s["name"] for s in resp.json()}
    assert names == {"Store 1", "Store 2"}


async def test_create_store_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/stores", json={"name": "Anonymous store"}
    )
    assert resp.status_code == 401


async def test_create_alias_backfills_raw_sales(client: AsyncClient, admin_ctx):
    """După import xlsx, raw_sales au store_id=NULL. Crearea unui alias
    pentru raw_client trebuie să backfill-uie store_id pe rândurile existente.
    """
    # 1) import xlsx cu 3 rânduri: 2 pe "DEDEMAN SRL", 1 pe "Altul SRL"
    rows = [
        sample_row(client="DEDEMAN SRL", amount=100),
        sample_row(client="DEDEMAN SRL", amount=200),
        sample_row(client="Altul SRL", amount=50),
    ]
    content = make_xlsx(rows)
    r_imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("data.xlsx", content, "application/octet-stream")},
    )
    assert r_imp.status_code == 200, r_imp.text
    assert r_imp.json()["inserted"] == 3

    # 2) unmapped → 2 group-uri (DEDEMAN SRL + Altul SRL)
    unm = await client.get("/api/stores/unmapped", headers=admin_ctx["headers"])
    assert unm.status_code == 200
    unm_data = {row["rawClient"]: row for row in unm.json()}
    assert unm_data["DEDEMAN SRL"]["rowCount"] == 2
    assert unm_data["Altul SRL"]["rowCount"] == 1

    # 3) creăm store + alias pentru "DEDEMAN SRL"
    store_resp = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Dedeman Pipera", "chain": "Dedeman"},
    )
    store_id = store_resp.json()["id"]
    alias_resp = await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "DEDEMAN SRL", "storeId": store_id},
    )
    assert alias_resp.status_code == 201

    # 4) unmapped scade — acum doar "Altul SRL"
    unm2 = await client.get("/api/stores/unmapped", headers=admin_ctx["headers"])
    rows_left = unm2.json()
    assert len(rows_left) == 1
    assert rows_left[0]["rawClient"] == "Altul SRL"


async def test_create_alias_duplicate_raw_client_409(
    client: AsyncClient, admin_ctx
):
    store_resp = await client.post(
        "/api/stores",
        headers=admin_ctx["headers"],
        json={"name": "Store X"},
    )
    store_id = store_resp.json()["id"]
    first = await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "SOME CLIENT", "storeId": store_id},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "SOME CLIENT", "storeId": store_id},
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "alias_exists"


async def test_create_alias_unknown_store_404(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/stores/aliases",
        headers=admin_ctx["headers"],
        json={"rawClient": "foo", "storeId": str(uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "store_not_found"


async def test_tenant_isolation_stores(client: AsyncClient, signup_user):
    """Tenant A nu vede stores-urile tenantului B."""
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")

    await client.post(
        "/api/stores",
        headers=a["headers"],
        json={"name": "A-Store"},
    )
    await client.post(
        "/api/stores",
        headers=b["headers"],
        json={"name": "B-Store"},
    )

    list_a = await client.get("/api/stores", headers=a["headers"])
    names_a = {s["name"] for s in list_a.json()}
    assert names_a == {"A-Store"}

    list_b = await client.get("/api/stores", headers=b["headers"])
    names_b = {s["name"] for s in list_b.json()}
    assert names_b == {"B-Store"}


async def test_tenant_isolation_alias_cross_store_404(
    client: AsyncClient, signup_user
):
    """Tenant A nu poate crea alias pointând la un store din tenant B."""
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")
    b_store = await client.post(
        "/api/stores",
        headers=b["headers"],
        json={"name": "B-Store"},
    )
    b_store_id = b_store.json()["id"]

    resp = await client.post(
        "/api/stores/aliases",
        headers=a["headers"],
        json={"rawClient": "cross tenant", "storeId": b_store_id},
    )
    # Tenant A nu "vede" store-ul B → 404 (nu 403, nu leak-uim existența)
    assert resp.status_code == 404


async def test_merge_stores_consolidates_aliases_and_sales(
    client: AsyncClient, admin_ctx
):
    """Merge store B into A: aliases + raw_sales + assignments mută, B dispare."""
    # Create primary + duplicate stores
    p = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "Dedeman Pipera"})
    d = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "Dedeman Pipera V2"})
    primary_id, dup_id = p.json()["id"], d.json()["id"]

    # Import sales → alias raw→dup → sales get dup.store_id
    rows = [sample_row(client="DED PIPERA V2", amount=100)]
    await client.post("/api/sales/import", headers=admin_ctx["headers"],
                     files={"file": ("x.xlsx", make_xlsx(rows), "application/octet-stream")})
    await client.post("/api/stores/aliases", headers=admin_ctx["headers"],
                     json={"rawClient": "DED PIPERA V2", "storeId": dup_id})

    # Merge dup into primary
    m = await client.post("/api/stores/merge", headers=admin_ctx["headers"],
                         json={"primaryId": primary_id, "duplicateIds": [dup_id]})
    assert m.status_code == 200, m.text
    body = m.json()
    assert body["mergedCount"] == 1
    assert body["aliasesReassigned"] == 1
    assert body["salesReassigned"] == 1

    # Dup gone, primary remains
    stores = await client.get("/api/stores", headers=admin_ctx["headers"])
    ids = {s["id"] for s in stores.json()}
    assert primary_id in ids
    assert dup_id not in ids

    # Alias now points to primary
    aliases = await client.get("/api/stores/aliases", headers=admin_ctx["headers"])
    assert aliases.json()[0]["storeId"] == primary_id


async def test_merge_stores_tenant_isolation(client: AsyncClient, signup_user):
    """Admin in tenant A nu poate merge-ui stores din tenant B."""
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")
    pa = await client.post("/api/stores", headers=a["headers"], json={"name": "A1"})
    db = await client.post("/api/stores", headers=b["headers"], json={"name": "B2"})

    # A tries to merge B's store into A's store → duplicate not found for A
    resp = await client.post("/api/stores/merge", headers=a["headers"],
                            json={"primaryId": pa.json()["id"], "duplicateIds": [db.json()["id"]]})
    assert resp.status_code == 404


async def test_bulk_set_active(client: AsyncClient, admin_ctx):
    """Admin poate dezactiva/activa magazine multiple simultan."""
    a = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "S1"})
    b = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "S2"})
    c = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "S3"})

    # Dezactivează S1 + S2
    resp = await client.post(
        "/api/stores/bulk-set-active",
        headers=admin_ctx["headers"],
        json={"ids": [a.json()["id"], b.json()["id"]], "active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    # Verifică
    stores = await client.get("/api/stores", headers=admin_ctx["headers"])
    by_name = {s["name"]: s for s in stores.json()}
    assert by_name["S1"]["active"] is False
    assert by_name["S2"]["active"] is False
    assert by_name["S3"]["active"] is True  # neatins


async def test_bulk_set_active_tenant_isolation(client: AsyncClient, signup_user):
    """Admin în tenant A nu poate modifica stores din tenant B."""
    a = await signup_user(tenant_name="Alpha Corp")
    b = await signup_user(tenant_name="Beta Corp")
    store_b = await client.post("/api/stores", headers=b["headers"], json={"name": "B-Store"})

    resp = await client.post(
        "/api/stores/bulk-set-active",
        headers=a["headers"],
        json={"ids": [store_b.json()["id"]], "active": False},
    )
    # Tenant A nu vede store-ul B → `updated` = 0 (silent, nu leak existența)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0
