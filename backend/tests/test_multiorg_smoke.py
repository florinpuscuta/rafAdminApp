"""Smoke tests pentru refactor-urile multi-org.

Verifică:
1. GET endpoints refactorate la `get_current_org_ids` întorc 200 (nu 500)
   — atât în mod single-org default cât și cu `X-Active-Org-Id: <uuid>`.
2. Header `X-Active-Org-Id: all` (SIKADP consolidated) e acceptat și nu
   produce eroare pe endpoints care iterează `org_ids`.
3. Tenant isolation: 2 useri din 2 tenants nu se văd reciproc datele.

Refactor-ul scope: sales, stores, agents, products, comenzi_fara_ind, ai.
Cat 2 (mkt_*, rapoarte_*, bonusari, etc.) — adăugate când agenții termină.
"""
from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# Endpoint-urile care au fost refactorate la get_current_org_ids.
# Format: (method, path, expected_status_OR_acceptable_set)
_REFACTORED_GET_ENDPOINTS: list[tuple[str, int | set[int]]] = [
    ("/api/sales?page=1&pageSize=10", 200),
    ("/api/sales/batches", 200),
    ("/api/sales/export", {200, 422}),  # 422 dacă lipsesc params
    ("/api/stores", 200),
    ("/api/stores/chains", 200),
    ("/api/stores/aliases", 200),
    ("/api/stores/unmapped", 200),
    ("/api/stores/unmapped/suggestions", 200),
    ("/api/agents", 200),
    ("/api/agents/aliases", 200),
    ("/api/agents/unmapped", 200),
    ("/api/agents/assignments", 200),
    ("/api/products", 200),
    ("/api/products/categories", 200),
    ("/api/products/aliases", 200),
    ("/api/products/unmapped", 200),
    ("/api/comenzi-fara-ind?scope=adp", {200, 404}),  # 404 dacă nu există snapshot
    ("/api/ai/conversations", 200),
]


@pytest.mark.parametrize("path,expected", _REFACTORED_GET_ENDPOINTS)
async def test_refactored_endpoints_default_org(
    client: AsyncClient, admin_ctx, path: str, expected,
):
    """Toate endpoint-urile multi-org refactorate trebuie să răspundă fără
    auth header `X-Active-Org-Id` (= default = home tenant). Status acceptabil
    e 200 (sau set explicit pentru cazuri cu params lipsă)."""
    resp = await client.get(path, headers=admin_ctx["headers"])
    if isinstance(expected, set):
        assert resp.status_code in expected, (
            f"GET {path}: got {resp.status_code} expected one of {expected}\n"
            f"body: {resp.text[:300]}"
        )
    else:
        assert resp.status_code == expected, (
            f"GET {path}: got {resp.status_code} expected {expected}\n"
            f"body: {resp.text[:300]}"
        )


@pytest.mark.parametrize("path,expected", _REFACTORED_GET_ENDPOINTS)
async def test_refactored_endpoints_active_org_explicit(
    client: AsyncClient, admin_ctx, path: str, expected,
):
    """Cu `X-Active-Org-Id: <home_tenant_uuid>` rezultatul e identic cu default."""
    home_tid = admin_ctx["tenant"]["id"]
    headers = {**admin_ctx["headers"], "X-Active-Org-Id": str(home_tid)}
    resp = await client.get(path, headers=headers)
    if isinstance(expected, set):
        assert resp.status_code in expected, resp.text[:300]
    else:
        assert resp.status_code == expected, resp.text[:300]


@pytest.mark.parametrize("path,expected", _REFACTORED_GET_ENDPOINTS)
async def test_refactored_endpoints_active_org_all_sentinel(
    client: AsyncClient, admin_ctx, path: str, expected,
):
    """Cu `X-Active-Org-Id: all` (SIKADP consolidated) endpoint-urile nu
    trebuie să cadă cu 500. Pentru un user cu o singură organizație,
    rezultatul e identic cu default."""
    headers = {**admin_ctx["headers"], "X-Active-Org-Id": "all"}
    resp = await client.get(path, headers=headers)
    assert resp.status_code != 500, (
        f"GET {path} cu all: 500 INTERNAL ERROR\n{resp.text[:500]}"
    )
    if isinstance(expected, set):
        assert resp.status_code in expected, resp.text[:300]
    else:
        assert resp.status_code == expected, resp.text[:300]


async def test_active_org_header_invalid_rejected(
    client: AsyncClient, admin_ctx,
):
    """Header invalid → 400."""
    headers = {**admin_ctx["headers"], "X-Active-Org-Id": "not-a-uuid"}
    resp = await client.get("/api/stores", headers=headers)
    assert resp.status_code == 400


async def test_active_org_header_other_tenant_rejected(
    client: AsyncClient, signup_user,
):
    """User-ul A trimite UUID-ul tenantului B → 403 (nu e membru)."""
    a = await signup_user(tenant_name="Org A")
    b = await signup_user(tenant_name="Org B")
    headers = {**a["headers"], "X-Active-Org-Id": str(b["tenant"]["id"])}
    resp = await client.get("/api/stores", headers=headers)
    assert resp.status_code == 403


async def test_tenant_isolation_stores(
    client: AsyncClient, signup_user,
):
    """Un store creat de admin A nu trebuie să apară pentru admin B."""
    a = await signup_user(tenant_name="Org A")
    b = await signup_user(tenant_name="Org B")

    r_create = await client.post(
        "/api/stores",
        headers=a["headers"],
        json={"name": "STORE_A_ONLY", "chain": "Dedeman"},
    )
    assert r_create.status_code == 201, r_create.text

    # B should NOT see it.
    r_b = await client.get("/api/stores", headers=b["headers"])
    assert r_b.status_code == 200
    names = {s["name"] for s in r_b.json()}
    assert "STORE_A_ONLY" not in names


async def test_ai_conversations_isolation(
    client: AsyncClient, signup_user,
):
    """Conversațiile sunt per-tenant."""
    a = await signup_user(tenant_name="Org A")
    b = await signup_user(tenant_name="Org B")

    r_create = await client.post(
        "/api/ai/conversations",
        headers=a["headers"],
        json={"title": "Conversatie A"},
    )
    assert r_create.status_code == 201

    r_b = await client.get("/api/ai/conversations", headers=b["headers"])
    assert r_b.status_code == 200
    titles = {c["title"] for c in r_b.json()}
    assert "Conversatie A" not in titles


async def test_ai_query_db_requires_authorized_tenant_uuid(
    client: AsyncClient, signup_user, db_session,
):
    """validate_sql cere ca SQL-ul să refere unul dintre tenant_id-urile autorizate.
    Este testat la nivel de unitate fără a invoca un provider AI real.
    """
    from uuid import uuid4
    from app.modules.ai.tools import validate_sql

    a = await signup_user(tenant_name="Org A")
    home_tid = UUID(a["tenant"]["id"])

    # SQL care folosește tenant_id-ul lui A → OK
    sql_ok = f"SELECT count(*) FROM raw_sales WHERE tenant_id = '{home_tid}'"
    assert validate_sql(sql_ok, [home_tid]) is None

    # SQL fără niciun UUID autorizat → eroare
    other = uuid4()
    sql_bad = f"SELECT count(*) FROM raw_sales WHERE tenant_id = '{other}'"
    err = validate_sql(sql_bad, [home_tid])
    assert err is not None
    assert "UUID" in err or "WHERE" in err

    # SQL cu IN multi-tenant care include UUID-ul autorizat → OK
    sql_in = f"SELECT count(*) FROM raw_sales WHERE tenant_id IN ('{home_tid}', '{other}')"
    assert validate_sql(sql_in, [home_tid]) is None


async def test_ai_write_tools_disabled(client: AsyncClient, db_session):
    """Tools-urile de scriere (propose_write, execute_write) au fost scoase
    din schemele expuse — nu mai sunt în ANTHROPIC_TOOLS / OPENAI_TOOLS."""
    from app.modules.ai.tools import ANTHROPIC_TOOLS, OPENAI_TOOLS

    anthropic_names = {t["name"] for t in ANTHROPIC_TOOLS}
    openai_names = {t["function"]["name"] for t in OPENAI_TOOLS}

    for name in ("propose_write", "execute_write"):
        assert name not in anthropic_names, (
            f"Anthropic încă expune {name}: {anthropic_names}"
        )
        assert name not in openai_names, (
            f"OpenAI încă expune {name}: {openai_names}"
        )

    # query_db + remember + forget + get_app_view trebuie să existe
    for name in ("query_db", "remember", "forget", "get_app_view"):
        assert name in anthropic_names, f"Lipsește {name} din Anthropic"
        assert name in openai_names, f"Lipsește {name} din OpenAI"


async def test_ai_dispatch_blocks_legacy_write_calls(db_session):
    """Chiar dacă AI încearcă să cheme propose_write/execute_write (din vechi
    cache de tool definitions), dispatch_tool refuză read-only mode."""
    from uuid import uuid4
    from app.modules.ai.tools import dispatch_tool

    fake_tid = uuid4()
    for name in ("propose_write", "execute_write"):
        result = await dispatch_tool(db_session, [fake_tid], name, {"sql": "DELETE FROM users", "token": "x"})
        assert "error" in result
        assert "read-only" in result["error"].lower()


async def test_app_views_registry_complete():
    """Sanity: registry-ul de view-uri are toate intrările cu doc + params_doc."""
    from app.modules.ai.app_views import VIEW_NAMES, _VIEWS

    assert len(VIEW_NAMES) >= 15, f"Prea puține view-uri: {len(VIEW_NAMES)}"
    for name in VIEW_NAMES:
        entry = _VIEWS[name]
        assert "fn" in entry
        assert callable(entry["fn"])
        assert entry.get("doc"), f"{name}: doc lipsă"
        assert entry.get("params_doc"), f"{name}: params_doc lipsă"
