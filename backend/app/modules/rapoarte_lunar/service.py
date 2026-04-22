"""Service pentru Raport Lunar Management.

Agregă date KA pentru (tenant, year, month) — refolosim serviciile deja
existente din `sales` și hidratăm nume prin `stores` / `agents`.

Nu atingem DB-ul direct; delegăm totul la servicii existente ca să păstrăm
consistența regulilor (ex. `_ka_filter`, agregare amount = sum).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents import service as agents_service
from app.modules.sales import service as sales_service
from app.modules.stores import service as stores_service


async def build_raport(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int,
    month: int,
) -> dict:
    # Totaluri luna
    kpis = await sales_service.overview_totals(
        session, tenant_id, year, month=month,
    )
    total_amount = Decimal(kpis["total_amount"])
    total_rows = int(kpis["total_rows"])
    has_data = total_rows > 0

    # Compară cu aceeași lună din year-1
    compare_amount: Decimal | None = None
    compare_rows: int | None = None
    pct_yoy: Decimal | None = None
    compare_kpis = await sales_service.overview_totals(
        session, tenant_id, year - 1, month=month,
    )
    compare_amount = Decimal(compare_kpis["total_amount"])
    compare_rows = int(compare_kpis["total_rows"])
    if compare_amount != 0:
        pct_yoy = ((total_amount - compare_amount) / compare_amount) * Decimal(100)

    # Top clients (10)
    store_rows = await sales_service.sum_by_store(
        session, tenant_id, year, limit=None, month=month,
    )
    # Top agents
    agent_rows = await sales_service.sum_by_agent(
        session, tenant_id, year, month=month,
    )

    sid_set = [sid for sid, _, _ in store_rows if sid is not None]
    aid_set = [aid for aid, _, _ in agent_rows if aid is not None]
    stores_map = await stores_service.get_many(session, tenant_id, sid_set)
    agents_map = await agents_service.get_many(session, tenant_id, aid_set)

    top_clients = []
    for sid, total, _ in store_rows[:10]:
        if sid is None:
            top_clients.append({
                "store_id": None, "store_name": "Nemapate",
                "chain": None, "total_amount": total,
            })
            continue
        s = stores_map.get(sid)
        top_clients.append({
            "store_id": str(sid),
            "store_name": s.name if s else str(sid),
            "chain": s.chain if s else None,
            "total_amount": total,
        })

    top_agents = []
    for aid, total, _ in agent_rows[:10]:
        if aid is None:
            top_agents.append({
                "agent_id": None, "agent_name": "Nemapați",
                "total_amount": total,
            })
            continue
        a = agents_map.get(aid)
        top_agents.append({
            "agent_id": str(aid),
            "agent_name": a.full_name if a else str(aid),
            "total_amount": total,
        })

    # Chain breakdown peste toate store-urile din luna
    chain_totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    chain_stores: dict[str, set] = defaultdict(set)
    for sid, total, _ in store_rows:
        if sid is None:
            key = "Nemapate"
        else:
            s = stores_map.get(sid)
            key = s.chain if s and s.chain else "Fără lanț"
            chain_stores[key].add(sid)
        chain_totals[key] += total
    chains = [
        {
            "chain": k,
            "store_count": len(chain_stores[k]),
            "total_amount": chain_totals[k],
        }
        for k in sorted(chain_totals.keys(), key=lambda c: chain_totals[c], reverse=True)
    ]

    return {
        "year": year,
        "month": month,
        "has_data": has_data,
        "kpis": {
            "total_amount": total_amount,
            "total_rows": total_rows,
            "distinct_stores": int(kpis["distinct_mapped_stores"]),
            "distinct_agents": int(kpis["distinct_mapped_agents"]),
            "compare_amount": compare_amount,
            "compare_rows": compare_rows,
            "pct_yoy": pct_yoy,
        },
        "top_clients": top_clients,
        "top_agents": top_agents,
        "chains": chains,
    }
