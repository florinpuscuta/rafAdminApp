"""
"Analiza pe luni" — breakdown lunar vânzări KA, anul curent vs anul precedent.

Pentru fiecare lună (1..12) și fiecare agent:
  - sales_y1 = vânzări an precedent (year-1)
  - sales_y2 = vânzări an curent (year)
  - diff    = sales_y2 - sales_y1  (+ = creștere)
  - pct     = diff / sales_y1 * 100 (None dacă y1 == 0)

Surse per scope (batch.source), grupate — dedup se aplică DOAR în interiorul
unui grup, grupurile se însumează:
  - adp    → [["sales_xlsx"]]
  - sika   → [["sika_mtd_xlsx", "sika_xlsx"]]   (MTD are prioritate)
  - sikadp → [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]

Rezolvarea (agent_id, store_id) canonic se face via SAM — identic cu vz_la_zi
(vezi `app.modules.mappings.resolution`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
from app.modules.sales.models import ImportBatch, RawSale


_MONTH_NAMES = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


def month_name(m: int) -> str:
    return _MONTH_NAMES[m] if 1 <= m <= 12 else ""


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]
_GROUPS_SIKADP: list[list[str]] = [
    ["sales_xlsx"],
    ["sika_mtd_xlsx", "sika_xlsx"],
]


@dataclass
class AgentMonthCell:
    month: int
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)


@dataclass
class AgentMonthly:
    agent_id: UUID | None
    agent_name: str
    months: dict[int, AgentMonthCell] = field(default_factory=dict)

    def cell(self, m: int) -> AgentMonthCell:
        return self.months.setdefault(m, AgentMonthCell(month=m))

    def totals(self) -> AgentMonthCell:
        y1 = sum((c.sales_y1 for c in self.months.values()), Decimal(0))
        y2 = sum((c.sales_y2 for c in self.months.values()), Decimal(0))
        return AgentMonthCell(month=0, sales_y1=y1, sales_y2=y2)


async def _sales_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Rânduri agregate pe (agent_id, store_id, client, year, month) pentru KA.

    Grupurile sunt disjuncte (se însumează). În cadrul unui grup, prioritatea
    e în ordinea listei — per (year, month) doar primul source cu date.

    `months_filter` restricționează lunile considerate (ex. {1..4} pentru YTD
    când suntem în aprilie). None = toate lunile.
    """
    year_prev = year_curr - 1
    out: dict[
        tuple[UUID | None, UUID | None, str | None, int, int],
        dict[str, Any],
    ] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            }
            if months_filter is not None:
                source_pairs = {(y, m) for (y, m) in source_pairs if m in months_filter}
            new_pairs = source_pairs - claimed_pairs
            if not new_pairs:
                continue

            new_years = {y for (y, _m) in new_pairs}
            new_months = {m for (_y, m) in new_pairs}
            stmt = (
                select(
                    RawSale.agent_id,
                    RawSale.store_id,
                    RawSale.client,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .group_by(
                    RawSale.agent_id, RawSale.store_id, RawSale.client,
                    RawSale.year, RawSale.month,
                )
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs:
                    continue
                key = (r.agent_id, r.store_id, r.client, int(r.year), int(r.month))
                row = out.setdefault(key, {
                    "agent_id": r.agent_id,
                    "store_id": r.store_id,
                    "client": r.client,
                    "year": int(r.year),
                    "month": int(r.month),
                    "amount": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)

            claimed_pairs |= new_pairs

    return list(out.values())


async def _hydrate_agent_names(
    session: AsyncSession,
    tenant_id: UUID,
    agent_ids: set[UUID],
) -> dict[UUID, str]:
    if not agent_ids:
        return {}
    rows = (await session.execute(
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.id.in_(agent_ids))
    )).all()
    return {r[0]: r[1] for r in rows}


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


# ── Core aggregation ─────────────────────────────────────────────────────


async def _months_with_data(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int,
    batch_source_groups: list[list[str]],
) -> set[int]:
    """Distinct luni cu date KA în `year`, unite peste toate source-urile din
    `batch_source_groups`. Folosit pentru auto-YTD: comparăm ambii ani doar
    pe lunile care EXISTĂ în year_curr (ex. dacă Apr 2026 e în DB, includem
    Apr; dacă Mai 2026 lipsește, îl excludem și din Mai 2025)."""
    sources = {s for g in batch_source_groups for s in g}
    if not sources:
        return set()
    stmt = (
        select(RawSale.month)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year == year,
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
        )
        .distinct()
    )
    return {int(r.month) for r in (await session.execute(stmt)).all()}


async def _build_agents(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None = None,
) -> list[AgentMonthly]:
    year_prev = year_curr - 1

    # Auto-YTD: dacă nu e filtru explicit, restricționăm la lunile cu date
    # în year_curr — ca să comparăm "perioade similare" (ex. Ian-Apr 2025
    # vs Ian-Apr 2026, excluzând Mai-Dec care n-au corespondent în 2026).
    if months_filter is None:
        months_filter = await _months_with_data(
            session, tenant_id,
            year=year_curr, batch_source_groups=batch_source_groups,
        )

    rows = await _sales_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        months_filter=months_filter,
    )

    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"]
        for r in rows
        if r["agent_id"] is None and r["store_id"] is not None
    }
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    by_agent: dict[UUID | None, AgentMonthly] = {}
    for r in rows:
        resolved_agent, _resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )
        ar = by_agent.setdefault(
            resolved_agent,
            AgentMonthly(agent_id=resolved_agent, agent_name=""),
        )
        cell = ar.cell(r["month"])
        if r["year"] == year_prev:
            cell.sales_y1 += r["amount"]
        elif r["year"] == year_curr:
            cell.sales_y2 += r["amount"]

    agent_ids = {aid for aid in by_agent.keys() if aid is not None}
    agent_names = await _hydrate_agent_names(session, tenant_id, agent_ids)
    for aid, ar in by_agent.items():
        ar.agent_name = (
            agent_names.get(aid, "— nemapat —") if aid else "— nemapat —"
        )
        for m in range(1, 13):
            ar.cell(m)

    def _sort_key(a: AgentMonthly) -> tuple[int, Decimal]:
        is_unassigned = 1 if a.agent_id is None else 0
        return (is_unassigned, -a.totals().sales_y2)

    return sorted(by_agent.values(), key=_sort_key)


# ── Public entry-points ──────────────────────────────────────────────────


async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    months_filter: set[int] | None = None,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_ADP,
        months_filter=months_filter,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_ADP for s in g],
    )
    return {
        "scope": "adp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "agents": agents,
    }


async def get_for_sika(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    months_filter: set[int] | None = None,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_SIKA,
        months_filter=months_filter,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKA for s in g],
    )
    return {
        "scope": "sika",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "agents": agents,
    }


async def get_for_sikadp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    months_filter: set[int] | None = None,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_SIKADP,
        months_filter=months_filter,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKADP for s in g],
    )
    return {
        "scope": "sikadp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "agents": agents,
    }
