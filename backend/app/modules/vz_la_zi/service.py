"""
"Vz la zi" — Radiografie luna curentă vs aceeași lună an anterior.

Agregă pe agent + magazin:
  - prev_sales: vânzări full luna precedentă (year-1, aceeași lună)
  - curr_sales: MTD luna curentă
  - orders: comenzi open (ADP: NELIVRAT + NEFACTURAT separat; SIKA: OPEN total)
  - exercitiu = curr_sales + orders
  - realizare% = exercitiu / prev_sales * 100
  - gap = exercitiu - prev_sales  (pozitiv = overachievement)

Surse per scope:
  - adp    → raw_sales (source='sales_xlsx') + raw_orders (source='adp')
  - sika   → raw_sales (source='sika_mtd_xlsx' pt. MTD + prev_sales, fallback 'sika_xlsx')
             + raw_orders (source='sika')
  - sikadp → combină ambele
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
from app.modules.orders.models import RawOrder
from app.modules.sales.models import ImportBatch, RawSale
from app.modules.stores.models import Store


_MONTH_NAMES = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


def month_name(m: int) -> str:
    return _MONTH_NAMES[m] if 1 <= m <= 12 else ""


@dataclass
class StoreRow:
    store_id: UUID | None
    store_name: str
    prev_sales: Decimal = Decimal(0)
    curr_sales: Decimal = Decimal(0)
    nelivrate: Decimal = Decimal(0)
    nefacturate: Decimal = Decimal(0)

    @property
    def orders_total(self) -> Decimal:
        return self.nelivrate + self.nefacturate

    @property
    def exercitiu(self) -> Decimal:
        return self.curr_sales + self.orders_total


@dataclass
class AgentRow:
    agent_id: UUID | None
    agent_name: str
    stores: dict[UUID | None, StoreRow] = field(default_factory=dict)

    @property
    def stores_count(self) -> int:
        return len(self.stores)

    def totals(self) -> dict[str, Decimal]:
        prev = sum((s.prev_sales for s in self.stores.values()), Decimal(0))
        curr = sum((s.curr_sales for s in self.stores.values()), Decimal(0))
        neliv = sum((s.nelivrate for s in self.stores.values()), Decimal(0))
        nefact = sum((s.nefacturate for s in self.stores.values()), Decimal(0))
        return {
            "prev_sales": prev,
            "curr_sales": curr,
            "nelivrate": neliv,
            "nefacturate": nefact,
            "orders_total": neliv + nefact,
            "exercitiu": curr + neliv + nefact,
        }


# ── Helper: resolve canonical name maps ──────────────────────────────────

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


# ── Core aggregation ──────────────────────────────────────────────────────

async def _sales_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int,
    batch_sources: list[str],
) -> list[dict[str, Any]]:
    """
    Returnează rânduri [{agent_id, store_id, client, prev_sales, curr_sales}]
    agregat pe (agent_id, store_id, client) pe KA channel pentru luna+anul
    cerut și anul precedent (aceeași lună). `client` e inclus ca să permită
    fallback-ul de rezolvare agent/store via SAM în `_build_rows`.

    `batch_sources` e ordonat pe PRIORITATE (primul = preferat). Pentru fiecare
    (year, month), folosim DOAR source-ul cu prioritatea cea mai mare care
    conține date — previne double-counting când sika_xlsx și sika_mtd_xlsx
    acoperă aceeași perioadă (ex. Apr 2025 prezent în ambele).
    """
    year_prev = year_curr - 1
    all_rows: dict[tuple[UUID | None, UUID | None, str | None], dict[str, Any]] = {}
    claimed_pairs: set[tuple[int, int]] = set()

    for src in batch_sources:
        # 1) Ce (year, month) pairs există în acest source pentru fereastra
        #    noastră (prev și curr an, aceeași lună)?
        pairs_stmt = (
            select(RawSale.year, RawSale.month)
            .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
            .where(
                RawSale.tenant_id == tenant_id,
                RawSale.year.in_([year_prev, year_curr]),
                RawSale.month == month,
                func.upper(RawSale.channel) == "KA",
                ImportBatch.source == src,
            )
            .distinct()
        )
        source_pairs = {
            (int(r.year), int(r.month))
            for r in (await session.execute(pairs_stmt)).all()
        }
        new_pairs = source_pairs - claimed_pairs
        if not new_pairs:
            continue

        # 2) Agregăm DOAR pentru (year, month) neclaimate, din acest source.
        sales_prev = func.coalesce(
            func.sum(case((RawSale.year == year_prev, RawSale.amount), else_=0)), 0
        )
        sales_curr = func.coalesce(
            func.sum(case((RawSale.year == year_curr, RawSale.amount), else_=0)), 0
        )
        new_years = {y for (y, _m) in new_pairs}
        stmt = (
            select(
                RawSale.agent_id,
                RawSale.store_id,
                RawSale.client,
                sales_prev.label("prev_sales"),
                sales_curr.label("curr_sales"),
            )
            .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
            .where(
                RawSale.tenant_id == tenant_id,
                RawSale.year.in_(new_years),
                RawSale.month == month,
                func.upper(RawSale.channel) == "KA",
                ImportBatch.source == src,
            )
            .group_by(RawSale.agent_id, RawSale.store_id, RawSale.client)
        )
        result = await session.execute(stmt)
        for r in result.all():
            key = (r.agent_id, r.store_id, r.client)
            row = all_rows.setdefault(key, {
                "agent_id": r.agent_id,
                "store_id": r.store_id,
                "client": r.client,
                "prev_sales": Decimal(0),
                "curr_sales": Decimal(0),
            })
            row["prev_sales"] += Decimal(r.prev_sales or 0)
            row["curr_sales"] += Decimal(r.curr_sales or 0)

        claimed_pairs |= new_pairs

    return list(all_rows.values())


async def _latest_report_date(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    source: str,
) -> date | None:
    stmt = select(func.max(RawOrder.report_date)).where(
        RawOrder.tenant_id == tenant_id, RawOrder.source == source
    )
    result = (await session.execute(stmt)).scalar_one_or_none()
    return result


async def _orders_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    source: str,
    report_date: date,
) -> list[dict[str, Any]]:
    """
    Returnează [{agent_id, store_id, client, nelivrate, nefacturate}] agregat
    pe (agent_id, store_id, client) la nivelul snapshot-ului dat. `client` e
    inclus pentru fallback via SAM în `_build_rows`. `nelivrate` include
    status NELIVRAT (ADP) sau OPEN (Sika). `nefacturate` = doar status
    NEFACTURAT (ADP; gol pt. Sika).

    ADP: `nelivrate` include TOATE comenzile NELIVRAT/OPEN (cu și fără IND).
    `nefacturate` rămâne doar pentru cele cu IND — fără IND n-au factură încă.
    """
    if source == "adp":
        neliv_status_expr = case(
            (RawOrder.status.in_(("NELIVRAT", "OPEN")), RawOrder.remaining_amount),
            else_=0,
        )
        nefact_status_expr = case(
            (
                (RawOrder.status == "NEFACTURAT") & (RawOrder.has_ind == True),
                RawOrder.remaining_amount,
            ),
            else_=0,
        )
    else:
        neliv_status_expr = case(
            (RawOrder.status.in_(("NELIVRAT", "OPEN")), RawOrder.remaining_amount),
            else_=0,
        )
        nefact_status_expr = case(
            (RawOrder.status == "NEFACTURAT", RawOrder.remaining_amount),
            else_=0,
        )
    neliv_expr = func.coalesce(func.sum(neliv_status_expr), 0)
    nefact_expr = func.coalesce(func.sum(nefact_status_expr), 0)
    stmt = (
        select(
            RawOrder.agent_id,
            RawOrder.store_id,
            RawOrder.client,
            neliv_expr.label("nelivrate"),
            nefact_expr.label("nefacturate"),
        )
        .where(
            RawOrder.tenant_id == tenant_id,
            RawOrder.source == source,
            RawOrder.report_date == report_date,
        )
        .group_by(RawOrder.agent_id, RawOrder.store_id, RawOrder.client)
    )
    result = await session.execute(stmt)
    return [
        {
            "agent_id": r.agent_id,
            "store_id": r.store_id,
            "client": r.client,
            "nelivrate": Decimal(r.nelivrate or 0),
            "nefacturate": Decimal(r.nefacturate or 0),
        }
        for r in result.all()
    ]


async def _last_update(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    sources: list[str],
) -> datetime | None:
    stmt = select(func.max(ImportBatch.created_at)).where(
        ImportBatch.tenant_id == tenant_id,
        ImportBatch.source.in_(sources),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _ind_counts(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    report_date: date,
) -> tuple[int, int]:
    """Doar ADP: (processed_count, missing_count, processed_amount, missing_amount)
    pentru has_ind true/false. Sumele folosesc remaining_amount (valoarea nelivrată)
    ca să reflecte cât mai e de livrat cu/fără IND."""
    stmt = select(
        func.sum(case((RawOrder.has_ind == True, 1), else_=0)),
        func.sum(case((RawOrder.has_ind == False, 1), else_=0)),
        func.coalesce(
            func.sum(case((RawOrder.has_ind == True, RawOrder.remaining_amount), else_=0)),
            0,
        ),
        func.coalesce(
            func.sum(case((RawOrder.has_ind == False, RawOrder.remaining_amount), else_=0)),
            0,
        ),
    ).where(
        RawOrder.tenant_id == tenant_id,
        RawOrder.source == "adp",
        RawOrder.report_date == report_date,
    )
    row = (await session.execute(stmt)).one()
    return (
        int(row[0] or 0),
        int(row[1] or 0),
        Decimal(row[2] or 0),
        Decimal(row[3] or 0),
    )


# ── Scope orchestrators ──────────────────────────────────────────────────

async def _build_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int,
    sales_batch_sources: list[str],
    orders_source: str | None,
) -> tuple[dict[tuple[UUID | None, UUID | None], StoreRow], date | None]:
    """
    Construiește maparea (agent_id, store_id) → StoreRow.
    Returnează și report_date folosit (None dacă nu există comenzi).
    """
    by_key: dict[tuple[UUID | None, UUID | None], StoreRow] = {}

    sales = await _sales_rows(
        session, tenant_id, year_curr=year_curr, month=month,
        batch_sources=sales_batch_sources,
    )

    report_date = None
    orders: list[dict[str, Any]] = []
    if orders_source:
        report_date = await _latest_report_date(session, tenant_id, source=orders_source)
        if report_date is not None:
            orders = await _orders_rows(
                session, tenant_id, source=orders_source, report_date=report_date,
            )

    # Rezolvare agent + store canonic via SAM. Detalii în
    # app/modules/mappings/resolution.py.
    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = set()
    for r in sales:
        if r["agent_id"] is None and r["store_id"] is not None:
            store_ids_to_resolve.add(r["store_id"])
    for r in orders:
        if r["agent_id"] is None and r["store_id"] is not None:
            store_ids_to_resolve.add(r["store_id"])
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    for r in sales:
        resolved_agent, resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )
        key = (resolved_agent, resolved_store)
        sr = by_key.setdefault(key, StoreRow(store_id=resolved_store, store_name=""))
        sr.prev_sales += r["prev_sales"]
        sr.curr_sales += r["curr_sales"]

    for r in orders:
        resolved_agent, resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )
        key = (resolved_agent, resolved_store)
        sr = by_key.setdefault(key, StoreRow(store_id=resolved_store, store_name=""))
        sr.nelivrate += r["nelivrate"]
        sr.nefacturate += r["nefacturate"]

    return by_key, report_date


def _agents_list(
    rows: dict[tuple[UUID | None, UUID | None], StoreRow],
    agent_names: dict[UUID, str],
    store_names: dict[UUID, str],
) -> list[AgentRow]:
    by_agent: dict[UUID | None, AgentRow] = {}
    for (agent_id, store_id), sr in rows.items():
        sr.store_name = store_names.get(store_id, "—") if store_id else "— nemapat —"
        ar = by_agent.setdefault(
            agent_id,
            AgentRow(
                agent_id=agent_id,
                agent_name=agent_names.get(agent_id, "— nemapat —") if agent_id else "— nemapat —",
            ),
        )
        ar.stores[store_id] = sr

    # Sortează agenții descendent după exercițiu; magazinele descendent după exercițiu
    sorted_agents = sorted(
        by_agent.values(),
        key=lambda a: a.totals()["exercitiu"],
        reverse=True,
    )
    for a in sorted_agents:
        a.stores = dict(
            sorted(a.stores.items(), key=lambda kv: kv[1].exercitiu, reverse=True)
        )
    return sorted_agents


def _kpis(agents: list[AgentRow]) -> dict[str, Decimal]:
    prev = Decimal(0)
    curr = Decimal(0)
    neliv = Decimal(0)
    nefact = Decimal(0)
    for a in agents:
        t = a.totals()
        prev += t["prev_sales"]
        curr += t["curr_sales"]
        neliv += t["nelivrate"]
        nefact += t["nefacturate"]
    exerc = curr + neliv + nefact
    return {
        "prev_sales": prev,
        "curr_sales": curr,
        "nelivrate": neliv,
        "nefacturate": nefact,
        "orders_total": neliv + nefact,
        "exercitiu": exerc,
        "gap": exerc - prev,
    }


# ── Public entry-points ──────────────────────────────────────────────────

async def get_for_adp(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int,
) -> dict[str, Any]:
    rows, report_date = await _build_rows(
        session, tenant_id,
        year_curr=year_curr, month=month,
        sales_batch_sources=["sales_xlsx"],
        orders_source="adp",
    )
    agent_ids = {k[0] for k in rows.keys() if k[0] is not None}
    store_ids = {k[1] for k in rows.keys() if k[1] is not None}
    agent_names, store_names = await _hydrate_names(
        session, tenant_id, agent_ids=agent_ids, store_ids=store_ids,
    )
    agents = _agents_list(rows, agent_names, store_names)
    kpis = _kpis(agents)

    ind_processed = ind_missing = 0
    ind_processed_amount = Decimal(0)
    ind_missing_amount = Decimal(0)
    if report_date is not None:
        ind_processed, ind_missing, ind_processed_amount, ind_missing_amount = await _ind_counts(
            session, tenant_id, report_date=report_date,
        )

    last_update = await _last_update(
        session, tenant_id, sources=["sales_xlsx", "orders_adp"]
    )
    return {
        "scope": "adp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "month": month,
        "month_name": month_name(month),
        "report_date": report_date,
        "last_update": last_update,
        "kpis": kpis,
        "ind_processed": ind_processed,
        "ind_missing": ind_missing,
        "ind_processed_amount": ind_processed_amount,
        "ind_missing_amount": ind_missing_amount,
        "agents": agents,
    }


async def get_for_sika(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int,
) -> dict[str, Any]:
    # Sika: prefer sika_mtd (MTD + prev full-month), fallback la sika_xlsx.
    rows, report_date = await _build_rows(
        session, tenant_id,
        year_curr=year_curr, month=month,
        sales_batch_sources=["sika_mtd_xlsx", "sika_xlsx"],
        orders_source="sika",
    )
    agent_ids = {k[0] for k in rows.keys() if k[0] is not None}
    store_ids = {k[1] for k in rows.keys() if k[1] is not None}
    agent_names, store_names = await _hydrate_names(
        session, tenant_id, agent_ids=agent_ids, store_ids=store_ids,
    )
    agents = _agents_list(rows, agent_names, store_names)
    kpis = _kpis(agents)

    last_update = await _last_update(
        session, tenant_id, sources=["sika_mtd_xlsx", "sika_xlsx", "orders_sika"]
    )
    return {
        "scope": "sika",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "month": month,
        "month_name": month_name(month),
        "report_date": report_date,
        "last_update": last_update,
        "kpis": kpis,
        "agents": agents,
    }


async def get_for_sikadp(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int,
) -> dict[str, Any]:
    adp = await get_for_adp(session, tenant_id, year_curr=year_curr, month=month)
    sika = await get_for_sika(session, tenant_id, year_curr=year_curr, month=month)

    # Combinăm la nivel de (agent_id, store_id) unificat
    combined_rows: dict[tuple[UUID | None, UUID | None], StoreRow] = {}
    for src in (adp, sika):
        for a in src["agents"]:
            for store_id, sr in a.stores.items():
                key = (a.agent_id, store_id)
                existing = combined_rows.get(key)
                if existing is None:
                    combined_rows[key] = StoreRow(
                        store_id=sr.store_id,
                        store_name=sr.store_name,
                        prev_sales=sr.prev_sales,
                        curr_sales=sr.curr_sales,
                        nelivrate=sr.nelivrate,
                        nefacturate=sr.nefacturate,
                    )
                else:
                    existing.prev_sales += sr.prev_sales
                    existing.curr_sales += sr.curr_sales
                    existing.nelivrate += sr.nelivrate
                    existing.nefacturate += sr.nefacturate

    agent_ids = {k[0] for k in combined_rows.keys() if k[0] is not None}
    store_ids = {k[1] for k in combined_rows.keys() if k[1] is not None}
    agent_names, store_names = await _hydrate_names(
        session, tenant_id, agent_ids=agent_ids, store_ids=store_ids,
    )
    combined_agents = _agents_list(combined_rows, agent_names, store_names)
    combined_kpis = _kpis(combined_agents)

    last_update = await _last_update(
        session, tenant_id,
        sources=[
            "sales_xlsx", "sika_xlsx", "sika_mtd_xlsx",
            "orders_adp", "orders_sika",
        ],
    )

    return {
        "scope": "sikadp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "month": month,
        "month_name": month_name(month),
        "last_update": last_update,
        "combined": {
            "kpis": combined_kpis,
            "agents": combined_agents,
        },
        "adeplast": {
            "kpis": adp["kpis"],
            "ind_processed": adp["ind_processed"],
            "ind_missing": adp["ind_missing"],
            "ind_processed_amount": adp["ind_processed_amount"],
            "ind_missing_amount": adp["ind_missing_amount"],
            "report_date": adp["report_date"],
        },
        "sika": {
            "kpis": sika["kpis"],
            "report_date": sika["report_date"],
        },
    }
