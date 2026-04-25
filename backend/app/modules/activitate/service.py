"""
Service pentru Activitate Agenți — citește din tabelul `agent_visits`
(tenant-scoped) + rolează pe agent pentru response-ul agregat.

Suportă și adăugare de vizite (CRUD minim). Agenții care nu au nicio vizită
în interval tot apar, cu 0 vizite, pentru UI consistent.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activitate.models import AgentVisit
from app.modules.agents.models import Agent
from app.modules.stores.models import Store


async def get_activitate(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    return await get_activitate_by_tenants(
        session, [tenant_id],
        scope=scope, date_from=date_from, date_to=date_to,
    )


async def get_activitate_by_tenants(
    session: AsyncSession,
    tenant_ids: list[UUID],
    *,
    scope: str,
    date_from: date,
    date_to: date,
) -> dict[str, Any]:
    if not tenant_ids:
        return {
            "scope": scope, "date_from": date_from, "date_to": date_to,
            "agents_count": 0, "total_visits": 0, "total_stores": 0,
            "total_km": Decimal(0), "agents": [], "todo": None,
        }
    # 1) vizitele efective din DB pentru intervalul selectat
    visits_rows = (
        await session.execute(
            select(AgentVisit, Store.name)
            .outerjoin(Store, Store.id == AgentVisit.store_id)
            .where(
                AgentVisit.tenant_id.in_(tenant_ids),
                AgentVisit.scope == scope,
                AgentVisit.visit_date >= date_from,
                AgentVisit.visit_date <= date_to,
            )
            .order_by(AgentVisit.visit_date, AgentVisit.check_in)
        )
    ).all()

    # per agent: listă de vizite + totaluri
    by_agent: dict[UUID | None, dict[str, Any]] = defaultdict(
        lambda: {
            "visits": [],
            "total_km": Decimal(0),
            "total_duration_min": 0,
            "stores": set(),
        }
    )
    total_visits = 0
    total_stores: set[UUID | str] = set()
    total_km = Decimal(0)

    for v, store_name in visits_rows:
        row = {
            "visit_date": v.visit_date,
            "store_id": v.store_id,
            "store_name": store_name or v.client or "—",
            "client": v.client,
            "check_in": v.check_in,
            "check_out": v.check_out,
            "duration_min": v.duration_min,
            "km": v.km,
            "notes": v.notes,
            "photos_count": 0,
        }
        bucket = by_agent[v.agent_id]
        bucket["visits"].append(row)
        if v.km is not None:
            bucket["total_km"] += v.km
            total_km += v.km
        if v.duration_min is not None:
            bucket["total_duration_min"] += v.duration_min
        if v.store_id is not None:
            bucket["stores"].add(v.store_id)
            total_stores.add(v.store_id)
        elif v.client:
            bucket["stores"].add(v.client)
            total_stores.add(v.client)
        total_visits += 1

    # 2) lista canonică de agenți — îi afișăm pe toți, chiar dacă au 0 vizite
    agents_canonical = (
        await session.execute(
            select(Agent.id, Agent.full_name)
            .where(Agent.tenant_id.in_(tenant_ids))
            .order_by(Agent.full_name)
        )
    ).all()

    agents_out: list[dict[str, Any]] = []
    seen_ids: set[UUID | None] = set()
    for aid, aname in agents_canonical:
        bucket = by_agent.get(aid, {
            "visits": [],
            "total_km": Decimal(0),
            "total_duration_min": 0,
            "stores": set(),
        })
        agents_out.append({
            "agent_id": aid,
            "agent_name": aname,
            "visits_count": len(bucket["visits"]),
            "stores_count": len(bucket["stores"]),
            "total_km": bucket["total_km"],
            "total_duration_min": bucket["total_duration_min"],
            "visits": bucket["visits"],
        })
        seen_ids.add(aid)

    # agenți fără mapping (visits cu agent_id=None) — bucket special "—"
    orphan = by_agent.get(None)
    if orphan and orphan["visits"]:
        agents_out.append({
            "agent_id": None,
            "agent_name": "— fără mapping —",
            "visits_count": len(orphan["visits"]),
            "stores_count": len(orphan["stores"]),
            "total_km": orphan["total_km"],
            "total_duration_min": orphan["total_duration_min"],
            "visits": orphan["visits"],
        })

    return {
        "scope": scope,
        "date_from": date_from,
        "date_to": date_to,
        "agents_count": len(agents_out),
        "total_visits": total_visits,
        "total_stores": len(total_stores),
        "total_km": total_km,
        "agents": agents_out,
        "todo": None,
    }


async def create_visit(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    visit_date: date,
    agent_id: UUID | None,
    store_id: UUID | None,
    client: str | None,
    check_in: str | None,
    check_out: str | None,
    duration_min: int | None,
    km: Decimal | None,
    notes: str | None,
    created_by_user_id: UUID | None,
) -> AgentVisit:
    visit = AgentVisit(
        tenant_id=tenant_id,
        scope=scope,
        visit_date=visit_date,
        agent_id=agent_id,
        store_id=store_id,
        client=client,
        check_in=check_in,
        check_out=check_out,
        duration_min=duration_min,
        km=km,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    session.add(visit)
    await session.commit()
    await session.refresh(visit)
    return visit
