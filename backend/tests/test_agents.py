"""Teste pentru modulul agents: create, alias + backfill, multiple aliases
legate de același Agent (typo-uri).
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests._helpers import make_xlsx, sample_row


pytestmark = pytest.mark.asyncio


async def test_create_agent_201(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/agents",
        headers=admin_ctx["headers"],
        json={"fullName": "Ionut Filip", "email": "ionut@example.com"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["fullName"] == "Ionut Filip"
    assert data["email"] == "ionut@example.com"


async def test_create_agent_duplicate_409(client: AsyncClient, admin_ctx):
    payload = {"fullName": "Same Name"}
    first = await client.post(
        "/api/agents", headers=admin_ctx["headers"], json=payload
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/agents", headers=admin_ctx["headers"], json=payload
    )
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "agent_exists"


async def test_alias_backfills_agent_id_on_raw_sales(
    client: AsyncClient, admin_ctx
):
    # import cu 2 typo-uri pentru același om: "Ionut FIlip" + "Ionut Filip"
    rows = [
        sample_row(agent="Ionut FIlip", amount=100),
        sample_row(agent="Ionut Filip", amount=200),
        sample_row(agent="Altcineva", amount=50),
    ]
    content = make_xlsx(rows)
    r_imp = await client.post(
        "/api/sales/import",
        headers=admin_ctx["headers"],
        files={"file": ("data.xlsx", content, "application/octet-stream")},
    )
    assert r_imp.status_code == 200
    assert r_imp.json()["inserted"] == 3

    # unmapped = 3 group-uri (toți fără agent_id)
    unm = await client.get("/api/agents/unmapped", headers=admin_ctx["headers"])
    assert {r["rawAgent"] for r in unm.json()} == {
        "Ionut FIlip",
        "Ionut Filip",
        "Altcineva",
    }

    # creăm un Agent canonic + 2 alias-uri către el
    agent_resp = await client.post(
        "/api/agents",
        headers=admin_ctx["headers"],
        json={"fullName": "Ionut Filip"},
    )
    agent_id = agent_resp.json()["id"]

    a1 = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "Ionut FIlip", "agentId": agent_id},
    )
    a2 = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "Ionut Filip", "agentId": agent_id},
    )
    assert a1.status_code == 201
    assert a2.status_code == 201
    # ambele alias-uri → același agent canonic
    assert a1.json()["agentId"] == a2.json()["agentId"] == agent_id

    # unmapped → doar "Altcineva" rămâne
    unm2 = await client.get("/api/agents/unmapped", headers=admin_ctx["headers"])
    assert [r["rawAgent"] for r in unm2.json()] == ["Altcineva"]


async def test_two_aliases_can_point_to_same_agent(
    client: AsyncClient, admin_ctx
):
    """Sanity: AgentAlias NU are unique pe agent_id, deci pot exista N alias
    pentru 1 Agent canonic (scenariul typo-uri diferite)."""
    agent_resp = await client.post(
        "/api/agents",
        headers=admin_ctx["headers"],
        json={"fullName": "John Doe"},
    )
    agent_id = agent_resp.json()["id"]

    a1 = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "J. Doe", "agentId": agent_id},
    )
    a2 = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "Jon Doe", "agentId": agent_id},
    )
    assert a1.status_code == 201
    assert a2.status_code == 201

    aliases = await client.get(
        "/api/agents/aliases", headers=admin_ctx["headers"]
    )
    assert aliases.status_code == 200
    data = aliases.json()
    assert len(data) == 2
    assert all(a["agentId"] == agent_id for a in data)


async def test_create_alias_unknown_agent_404(client: AsyncClient, admin_ctx):
    resp = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "whatever", "agentId": str(uuid4())},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "agent_not_found"


async def test_create_alias_duplicate_raw_agent_409(
    client: AsyncClient, admin_ctx
):
    agent_resp = await client.post(
        "/api/agents",
        headers=admin_ctx["headers"],
        json={"fullName": "The Agent"},
    )
    agent_id = agent_resp.json()["id"]
    first = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "raw-x", "agentId": agent_id},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/agents/aliases",
        headers=admin_ctx["headers"],
        json={"rawAgent": "raw-x", "agentId": agent_id},
    )
    assert second.status_code == 409


async def test_agents_tenant_isolation(client: AsyncClient, signup_user):
    a = await signup_user(tenant_name="A Corp")
    b = await signup_user(tenant_name="B Corp")
    await client.post(
        "/api/agents",
        headers=a["headers"],
        json={"fullName": "Agent A"},
    )
    await client.post(
        "/api/agents",
        headers=b["headers"],
        json={"fullName": "Agent B"},
    )
    list_a = await client.get("/api/agents", headers=a["headers"])
    assert {x["fullName"] for x in list_a.json()} == {"Agent A"}


async def test_merge_agents_consolidates_sales_and_aliases(
    client: AsyncClient, admin_ctx
):
    from tests._helpers import make_xlsx, sample_row
    p = await client.post("/api/agents", headers=admin_ctx["headers"], json={"fullName": "Ionut Filip"})
    d = await client.post("/api/agents", headers=admin_ctx["headers"], json={"fullName": "Ionut FIlip"})
    primary_id, dup_id = p.json()["id"], d.json()["id"]

    rows = [sample_row(agent="FILIP IONUT", amount=500)]
    await client.post("/api/sales/import", headers=admin_ctx["headers"],
                     files={"file": ("x.xlsx", make_xlsx(rows), "application/octet-stream")})
    await client.post("/api/agents/aliases", headers=admin_ctx["headers"],
                     json={"rawAgent": "FILIP IONUT", "agentId": dup_id})

    m = await client.post("/api/agents/merge", headers=admin_ctx["headers"],
                         json={"primaryId": primary_id, "duplicateIds": [dup_id]})
    assert m.status_code == 200, m.text
    body = m.json()
    assert body["mergedCount"] == 1
    assert body["aliasesReassigned"] == 1
    assert body["salesReassigned"] == 1

    agents = await client.get("/api/agents", headers=admin_ctx["headers"])
    ids = {a["id"] for a in agents.json()}
    assert dup_id not in ids


async def test_merge_agents_dedupes_assignments(client: AsyncClient, admin_ctx):
    """Dacă Agent A și Agent B au ambii assignment la Store X, merge B→A păstrează doar un rând."""
    store = await client.post("/api/stores", headers=admin_ctx["headers"], json={"name": "S"})
    store_id = store.json()["id"]
    p = await client.post("/api/agents", headers=admin_ctx["headers"], json={"fullName": "Ag A"})
    d = await client.post("/api/agents", headers=admin_ctx["headers"], json={"fullName": "Ag B"})
    await client.post("/api/agents/assignments", headers=admin_ctx["headers"],
                     json={"agentId": p.json()["id"], "storeId": store_id})
    await client.post("/api/agents/assignments", headers=admin_ctx["headers"],
                     json={"agentId": d.json()["id"], "storeId": store_id})

    m = await client.post("/api/agents/merge", headers=admin_ctx["headers"],
                         json={"primaryId": p.json()["id"], "duplicateIds": [d.json()["id"]]})
    assert m.status_code == 200
    assert m.json()["assignmentsDeduped"] == 1

    assigns = await client.get("/api/agents/assignments", headers=admin_ctx["headers"])
    assert len(assigns.json()) == 1
