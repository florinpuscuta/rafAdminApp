"""
Service Foaia de Parcurs — generează + persistă foi per (tenant, scope, agent,
year, month).

Generator entries: fallback deterministic (distribuție liniară zile lucrătoare).
Logica AI din legacy nu e portată încă — flag `ai_generated=False`.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.agents.models import Agent
from app.modules.parcurs.models import (
    TravelSheet,
    TravelSheetEntry,
    TravelSheetFuelFill,
)
from app.modules.stores.models import Store


_MONTH_NAMES = {
    1: "Ianuarie", 2: "Februarie", 3: "Martie", 4: "Aprilie",
    5: "Mai", 6: "Iunie", 7: "Iulie", 8: "August",
    9: "Septembrie", 10: "Octombrie", 11: "Noiembrie", 12: "Decembrie",
}
_DAY_NAMES = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"]


async def list_agents(
    session: AsyncSession, tenant_id: UUID, *, scope: str,
) -> list[dict[str, Any]]:
    return await list_agents_by_tenants(session, [tenant_id], scope=scope)


async def list_agents_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID], *, scope: str,
) -> list[dict[str, Any]]:
    if not tenant_ids:
        return []
    subq = (
        select(Store.agent_id, func.count(Store.id).label("cnt"))
        .where(Store.tenant_id.in_(tenant_ids), Store.agent_id.isnot(None))
        .group_by(Store.agent_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(Agent.id, Agent.full_name, subq.c.cnt)
            .outerjoin(subq, subq.c.agent_id == Agent.id)
            .where(Agent.tenant_id.in_(tenant_ids))
            .order_by(Agent.full_name)
        )
    ).all()
    return [
        {"agent_id": r[0], "agent_name": r[1], "stores_count": int(r[2] or 0)}
        for r in rows
    ]


async def list_stores_for_agent(
    session: AsyncSession, tenant_id: UUID, *, scope: str, agent_name: str,
) -> list[dict[str, Any]]:
    return await list_stores_for_agent_by_tenants(
        session, [tenant_id], scope=scope, agent_name=agent_name,
    )


async def list_stores_for_agent_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID], *, scope: str, agent_name: str,
) -> list[dict[str, Any]]:
    if not tenant_ids:
        return []
    rows = (
        await session.execute(
            select(Store.id, Store.name)
            .join(Agent, Agent.id == Store.agent_id)
            .where(
                Agent.tenant_id.in_(tenant_ids),
                Store.tenant_id.in_(tenant_ids),
                Agent.full_name == agent_name,
            )
            .order_by(Store.name)
        )
    ).all()
    return [
        {"store_id": r[0], "store_name": r[1], "city": _extract_city(r[1])}
        for r in rows
    ]


def _extract_city(store_name: str) -> str | None:
    """Extrage orașul dintr-un nume de magazin tip 'DEDEMAN IASI 47'."""
    import re

    if not store_name:
        return None
    s = store_name.strip().upper()
    s = re.sub(r"\s+\d+$", "", s).strip()
    prefixes = [
        "DEDEMAN", "ALTEX", "HORNBACH", "LEROY MERLIN",
        "BRICOSTORE", "BRICO DEPOT", "PRAKTIKER", "MATHAUS", "AMBIENT",
    ]
    for p in sorted(prefixes, key=len, reverse=True):
        if s.startswith(p + " "):
            s = s[len(p):].strip()
            break
    return s.title() if s else None


def working_days(year: int, month: int) -> list[date]:
    days_in_month = calendar.monthrange(year, month)[1]
    return [
        date(year, month, d)
        for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() < 5
    ]


def _build_fallback_entries(
    year: int, month: int, km_start: int, km_end: int,
    stores: list[str],
) -> list[dict[str, Any]]:
    wd = working_days(year, month)
    if not wd:
        return []
    total_km = max(0, km_end - km_start)
    per_day = total_km // len(wd)
    remainder = total_km - per_day * len(wd)
    cur_km = km_start
    entries: list[dict[str, Any]] = []
    for i, d in enumerate(wd):
        km_this = per_day + (1 if i < remainder else 0)
        route = (
            f"Sediu → {stores[i % len(stores)]} → Sediu"
            if stores else "Sediu → Teren → Sediu"
        )
        entries.append({
            "entry_date": d,
            "day_name": _DAY_NAMES[d.weekday()],
            "route": route,
            "stores_visited": ",".join(stores[i % max(1, len(stores)):i % max(1, len(stores)) + 1]),
            "km_start": cur_km,
            "km_end": cur_km + km_this,
            "km_driven": km_this,
            "purpose": "Vizită comercială",
            "fuel_liters": None,
            "fuel_cost": None,
        })
        cur_km += km_this
    return entries


async def generate(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    req,
    created_by_user_id: UUID | None = None,
) -> dict[str, Any]:
    """Generează (fallback determinist) + persistă (upsert) foaia."""
    wd = working_days(req.year, req.month)
    num_days = len(wd) or 1
    total_km = max(0, req.km_end - req.km_start)
    total_fuel_liters = sum((Decimal(str(f.liters)) for f in req.fuel_fills), Decimal(0))
    total_fuel_cost = sum((Decimal(str(f.cost)) for f in req.fuel_fills), Decimal(0))

    # rezolvă agent_id dacă există
    agent_row = (
        await session.execute(
            select(Agent.id).where(
                Agent.tenant_id == tenant_id,
                Agent.full_name == req.agent,
            )
        )
    ).first()
    agent_id: UUID | None = agent_row[0] if agent_row else None

    # listă magazine pentru rute (best-effort)
    store_names: list[str] = []
    if agent_id is not None:
        store_rows = (
            await session.execute(
                select(Store.name)
                .where(Store.tenant_id == tenant_id, Store.agent_id == agent_id)
                .order_by(Store.name)
            )
        ).all()
        store_names = [r[0] for r in store_rows]

    entries_data = _build_fallback_entries(
        req.year, req.month, req.km_start, req.km_end, store_names,
    )

    # upsert pe (tenant, scope, agent_name, year, month)
    existing = (
        await session.execute(
            select(TravelSheet)
            .options(
                selectinload(TravelSheet.entries),
                selectinload(TravelSheet.fuel_fills),
            )
            .where(
                TravelSheet.tenant_id == tenant_id,
                TravelSheet.scope == req.scope,
                TravelSheet.agent_name == req.agent,
                TravelSheet.year == req.year,
                TravelSheet.month == req.month,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        sheet = TravelSheet(
            tenant_id=tenant_id,
            scope=req.scope,
            agent_id=agent_id,
            agent_name=req.agent,
            year=req.year,
            month=req.month,
            car_number=req.car_number,
            sediu=req.sediu,
            km_start=req.km_start,
            km_end=req.km_end,
            total_km=total_km,
            working_days=num_days,
            avg_km_per_day=Decimal(total_km) / Decimal(num_days) if num_days else Decimal(0),
            total_fuel_liters=total_fuel_liters,
            total_fuel_cost=total_fuel_cost,
            ai_generated=False,
            created_by_user_id=created_by_user_id,
        )
        session.add(sheet)
        await session.flush()
    else:
        sheet = existing
        sheet.agent_id = agent_id
        sheet.car_number = req.car_number
        sheet.sediu = req.sediu
        sheet.km_start = req.km_start
        sheet.km_end = req.km_end
        sheet.total_km = total_km
        sheet.working_days = num_days
        sheet.avg_km_per_day = Decimal(total_km) / Decimal(num_days) if num_days else Decimal(0)
        sheet.total_fuel_liters = total_fuel_liters
        sheet.total_fuel_cost = total_fuel_cost
        sheet.ai_generated = False
        # șterge entries + fuel_fills existente
        await session.execute(delete(TravelSheetEntry).where(TravelSheetEntry.sheet_id == sheet.id))
        await session.execute(delete(TravelSheetFuelFill).where(TravelSheetFuelFill.sheet_id == sheet.id))
        await session.flush()

    # inserează entries noi
    for e in entries_data:
        session.add(TravelSheetEntry(sheet_id=sheet.id, **e))

    # inserează fuel_fills noi
    for f in req.fuel_fills:
        try:
            fd = datetime.strptime(f.date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        session.add(TravelSheetFuelFill(
            sheet_id=sheet.id,
            fill_date=fd,
            liters=Decimal(str(f.liters)),
            cost=Decimal(str(f.cost)),
        ))

    await session.commit()

    return {
        "agent": req.agent,
        "month": req.month,
        "month_name": _MONTH_NAMES.get(req.month, str(req.month)),
        "year": req.year,
        "car_number": req.car_number,
        "sediu": req.sediu,
        "km_start": req.km_start,
        "km_end": req.km_end,
        "total_km": total_km,
        "working_days": num_days,
        "avg_km_per_day": float(Decimal(total_km) / Decimal(num_days)) if num_days else 0.0,
        "total_fuel_liters": float(total_fuel_liters),
        "total_fuel_cost": float(total_fuel_cost),
        "ai_generated": False,
        "entries": [
            {
                "date": e["entry_date"].strftime("%d.%m.%Y"),
                "day_name": e["day_name"],
                "route": e["route"],
                "stores_visited": [s for s in (e.get("stores_visited") or "").split(",") if s],
                "km_start": e["km_start"],
                "km_end": e["km_end"],
                "km_driven": e["km_driven"],
                "purpose": e["purpose"],
                "fuel_liters": float(e["fuel_liters"]) if e.get("fuel_liters") is not None else None,
                "fuel_cost": float(e["fuel_cost"]) if e.get("fuel_cost") is not None else None,
            }
            for e in entries_data
        ],
        "fuel_fills": [f.model_dump() for f in req.fuel_fills],
        "todo": None,
    }


async def list_sheets(
    session: AsyncSession, tenant_id: UUID, *, scope: str,
) -> list[dict[str, Any]]:
    return await list_sheets_by_tenants(session, [tenant_id], scope=scope)


async def list_sheets_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID], *, scope: str,
) -> list[dict[str, Any]]:
    """Listă foi existente per (tenants, scope), cele mai recente primele."""
    if not tenant_ids:
        return []
    rows = (
        await session.execute(
            select(TravelSheet)
            .where(TravelSheet.tenant_id.in_(tenant_ids), TravelSheet.scope == scope)
            .order_by(TravelSheet.year.desc(), TravelSheet.month.desc(), TravelSheet.agent_name)
        )
    ).scalars().all()
    return [
        {
            "id": s.id,
            "agent_name": s.agent_name,
            "year": s.year,
            "month": s.month,
            "month_name": _MONTH_NAMES.get(s.month, str(s.month)),
            "total_km": s.total_km,
            "working_days": s.working_days,
            "updated_at": s.updated_at,
        }
        for s in rows
    ]
