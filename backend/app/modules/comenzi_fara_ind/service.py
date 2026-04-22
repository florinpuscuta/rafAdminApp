"""
"Comenzi fără IND" — comenzi ADP deschise care n-au IND populat.

Definiție canonică (ex. `exercitiu_service.py` din legacy):
  not has_ind AND (status == 'NEFACTURAT' OR remaining_quantity > 0)

Răspunsul e grupat ierarhic:
  agents → orders → products (line items)

Așa user-ul vede unde sunt blocate comenzile pe agent, și poate expanda
fiecare comandă să vadă produsele.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
from app.modules.orders.models import RawOrder
from app.modules.stores.models import Store


@dataclass
class _Line:
    product_code: str | None
    product_name: str | None
    quantity: Decimal
    remaining_quantity: Decimal
    amount: Decimal
    remaining_amount: Decimal


@dataclass
class _OrderAgg:
    nr_comanda: str | None
    client_raw: str
    ship_to: str | None
    raw_agent_id: UUID | None
    raw_store_id: UUID | None
    # set după rezolvare SAM:
    agent_id: UUID | None = None
    store_id: UUID | None = None
    status: str | None = None
    data_livrare: str | None = None
    total_amount: Decimal = Decimal(0)
    total_remaining: Decimal = Decimal(0)
    lines: list[_Line] = field(default_factory=list)


async def _latest_report_date(
    session: AsyncSession, tenant_id: UUID,
) -> date | None:
    stmt = select(func.max(RawOrder.report_date)).where(
        RawOrder.tenant_id == tenant_id,
        RawOrder.source == "adp",
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _fetch_missing_ind_rows(
    session: AsyncSession, tenant_id: UUID, *, report_date: date,
) -> list[RawOrder]:
    """Rânduri raw_orders care satisfac definiția 'fără IND':
    not has_ind AND (status == 'NEFACTURAT' OR remaining_quantity > 0).
    """
    stmt = select(RawOrder).where(
        RawOrder.tenant_id == tenant_id,
        RawOrder.source == "adp",
        RawOrder.report_date == report_date,
        RawOrder.has_ind == False,  # noqa: E712
        or_(
            RawOrder.status == "NEFACTURAT",
            RawOrder.remaining_quantity > 0,
        ),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _group_by_order(rows: list[RawOrder]) -> dict[tuple[str | None, str], _OrderAgg]:
    """Agregă pe (nr_comanda, client). Păstrează produsele ca line items."""
    aggs: dict[tuple[str | None, str], _OrderAgg] = {}
    for r in rows:
        key = (r.nr_comanda, r.client)
        agg = aggs.get(key)
        if agg is None:
            agg = _OrderAgg(
                nr_comanda=r.nr_comanda,
                client_raw=r.client,
                ship_to=r.ship_to,
                raw_agent_id=r.agent_id,
                raw_store_id=r.store_id,
                status=r.status,
                data_livrare=r.data_livrare,
            )
            aggs[key] = agg
        agg.total_amount += Decimal(r.amount or 0)
        agg.total_remaining += Decimal(r.remaining_amount or 0)
        agg.lines.append(_Line(
            product_code=r.product_code,
            product_name=r.product_name,
            quantity=Decimal(r.quantity or 0),
            remaining_quantity=Decimal(r.remaining_quantity or 0),
            amount=Decimal(r.amount or 0),
            remaining_amount=Decimal(r.remaining_amount or 0),
        ))
        # Preferă primul non-null pe câmpurile "la nivel de comandă"
        if agg.ship_to is None and r.ship_to is not None:
            agg.ship_to = r.ship_to
        if agg.data_livrare is None and r.data_livrare is not None:
            agg.data_livrare = r.data_livrare
        if agg.raw_agent_id is None and r.agent_id is not None:
            agg.raw_agent_id = r.agent_id
        if agg.raw_store_id is None and r.store_id is not None:
            agg.raw_store_id = r.store_id
    return aggs


async def _hydrate_names(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    agent_ids: set[UUID],
    store_ids: set[UUID],
) -> tuple[dict[UUID, str], dict[UUID, str]]:
    agent_map: dict[UUID, str] = {}
    if agent_ids:
        rows = (await session.execute(
            select(Agent.id, Agent.full_name)
            .where(Agent.tenant_id == tenant_id, Agent.id.in_(agent_ids))
        )).all()
        agent_map = {r[0]: r[1] for r in rows}

    store_map: dict[UUID, str] = {}
    if store_ids:
        rows = (await session.execute(
            select(Store.id, Store.name)
            .where(Store.tenant_id == tenant_id, Store.id.in_(store_ids))
        )).all()
        store_map = {r[0]: r[1] for r in rows}
    return agent_map, store_map


async def get_for_adp(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    report_date: date | None = None,
) -> dict[str, Any]:
    effective_date = report_date or await _latest_report_date(session, tenant_id)
    if effective_date is None:
        return {
            "scope": "adp",
            "report_date": None,
            "total_orders": 0,
            "total_amount": Decimal(0),
            "total_remaining": Decimal(0),
            "agents": [],
        }

    raw_rows = await _fetch_missing_ind_rows(
        session, tenant_id, report_date=effective_date,
    )
    order_aggs = _group_by_order(raw_rows)

    # Rezolvare canonic (agent, store) via SAM
    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        a.raw_store_id for a in order_aggs.values()
        if a.raw_store_id is not None and a.raw_agent_id is None
    }
    sam_store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    for agg in order_aggs.values():
        final_agent, final_store = resolve_canonical(
            agent_id=agg.raw_agent_id,
            store_id=agg.raw_store_id,
            client=agg.client_raw,
            client_map=client_map,
            store_map=sam_store_map,
        )
        agg.agent_id = final_agent
        agg.store_id = final_store

    # Hydrate nume
    agent_ids = {a.agent_id for a in order_aggs.values() if a.agent_id}
    store_ids = {a.store_id for a in order_aggs.values() if a.store_id}
    agent_names, store_names = await _hydrate_names(
        session, tenant_id, agent_ids=agent_ids, store_ids=store_ids,
    )

    # Grupare ierarhică: agent → orders
    agents_map: dict[UUID | None, dict[str, Any]] = {}
    for agg in order_aggs.values():
        aid = agg.agent_id
        agent_entry = agents_map.setdefault(aid, {
            "agent_id": aid,
            "agent_name": (agent_names.get(aid) if aid else None) or "— nemapat —",
            "orders_count": 0,
            "total_amount": Decimal(0),
            "total_remaining": Decimal(0),
            "orders": [],
        })
        order_dict = {
            "nr_comanda": agg.nr_comanda,
            "client_raw": agg.client_raw,
            "ship_to": agg.ship_to,
            "store_id": agg.store_id,
            "store_name": (
                (store_names.get(agg.store_id) if agg.store_id else None)
                or "— nemapat —"
            ),
            "status": agg.status,
            "data_livrare": agg.data_livrare,
            "total_amount": agg.total_amount,
            "total_remaining": agg.total_remaining,
            "line_items_count": len(agg.lines),
            "products": [
                {
                    "product_code": ln.product_code,
                    "product_name": ln.product_name,
                    "quantity": ln.quantity,
                    "remaining_quantity": ln.remaining_quantity,
                    "amount": ln.amount,
                    "remaining_amount": ln.remaining_amount,
                }
                for ln in sorted(
                    agg.lines,
                    key=lambda x: float(x.remaining_amount or 0),
                    reverse=True,
                )
            ],
        }
        agent_entry["orders"].append(order_dict)
        agent_entry["orders_count"] += 1
        agent_entry["total_amount"] += agg.total_amount
        agent_entry["total_remaining"] += agg.total_remaining

    # Sortare: agenți neatribuiți la final, ceilalți desc după total_remaining
    for entry in agents_map.values():
        entry["orders"].sort(
            key=lambda o: float(o["total_remaining"] or 0), reverse=True,
        )

    agents_list = sorted(
        agents_map.values(),
        key=lambda e: (
            e["agent_id"] is None,  # nemapat la coadă
            -float(e["total_remaining"] or 0),
        ),
    )

    total_amount = sum((e["total_amount"] for e in agents_list), Decimal(0))
    total_remaining = sum((e["total_remaining"] for e in agents_list), Decimal(0))
    total_orders = sum(e["orders_count"] for e in agents_list)

    return {
        "scope": "adp",
        "report_date": effective_date,
        "total_orders": total_orders,
        "total_amount": total_amount,
        "total_remaining": total_remaining,
        "agents": agents_list,
    }


async def get_for_sika(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    report_date: date | None = None,
) -> dict[str, Any]:
    """IND e specific ADP. SIKA → listă goală."""
    return {
        "scope": "sika",
        "report_date": None,
        "total_orders": 0,
        "total_amount": Decimal(0),
        "total_remaining": Decimal(0),
        "agents": [],
    }
