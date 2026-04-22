"""
"Targhet" — targhet vs realizat pe 12 luni, per agent.

Pentru fiecare lună (1..12) și fiecare agent:
  - prev_sales = vânzări year-1 (an referință)
  - curr_sales = vânzări year (realizat)
  - target     = prev_sales × (1 + target_pct/100)
  - achievement_pct = curr_sales / target * 100
  - gap        = curr_sales - target

Surse per scope (batch.source):
  - adp    → ["sales_xlsx"]
  - sika   → ["sika_mtd_xlsx", "sika_xlsx"]   (MTD are prioritate)
  - sikadp → ambele, însumate

Rezolvarea (agent_id, store_id) canonic se face via SAM — identic cu
vz_la_zi (vezi `app.modules.mappings.resolution`).

NOTĂ model de date: legacy avea target global (un singur `target_pct`
stocat în DB). Pentru SaaS nu s-a definit încă tabel `targets` —
calculul derivă din raw_sales × multiplier. Când va exista tabel
`targets` dedicat, înlocuim `_compute_target()` cu lookup în acel
tabel (contractul API rămâne stabil). Vezi `__init__.py`.
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


# Default growth target (procent). Legacy folosea acelasi default.
DEFAULT_TARGET_PCT: Decimal = Decimal("10")

_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]
_GROUPS_SIKADP: list[list[str]] = [
    ["sales_xlsx"],
    ["sika_mtd_xlsx", "sika_xlsx"],
]


@dataclass
class MonthCell:
    month: int
    prev_sales: Decimal = Decimal(0)
    curr_sales: Decimal = Decimal(0)
    target_pct: Decimal = DEFAULT_TARGET_PCT

    @property
    def target(self) -> Decimal:
        return (self.prev_sales * (Decimal(100) + self.target_pct)) / Decimal(100)

    @property
    def gap(self) -> Decimal:
        return self.curr_sales - self.target

    @property
    def achievement_pct(self) -> Decimal | None:
        t = self.target
        if t == 0:
            return None
        return (self.curr_sales / t) * Decimal(100)


@dataclass
class AgentTarget:
    agent_id: UUID | None
    agent_name: str
    target_pct: Decimal = DEFAULT_TARGET_PCT
    months: dict[int, MonthCell] = field(default_factory=dict)

    def cell(self, m: int) -> MonthCell:
        return self.months.setdefault(m, MonthCell(month=m, target_pct=self.target_pct))

    def totals(self) -> MonthCell:
        prev = sum((c.prev_sales for c in self.months.values()), Decimal(0))
        curr = sum((c.curr_sales for c in self.months.values()), Decimal(0))
        return MonthCell(month=0, prev_sales=prev, curr_sales=curr, target_pct=self.target_pct)


# ── Sales aggregation (reutilizează logica dedup din analiza_pe_luni) ─────

async def _sales_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
) -> list[dict[str, Any]]:
    """Rânduri agregate pe (agent_id, store_id, client, year, month) pentru KA.

    Grupurile sunt disjuncte (se însumează). În cadrul unui grup, prioritatea
    e în ordinea listei — per (year, month) doar primul source cu date.
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


# ── Core builder ─────────────────────────────────────────────────────────

async def _build_agents(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    target_pct: Decimal,
) -> list[AgentTarget]:
    year_prev = year_curr - 1

    rows = await _sales_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
    )

    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"]
        for r in rows
        if r["agent_id"] is None and r["store_id"] is not None
    }
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    by_agent: dict[UUID | None, AgentTarget] = {}
    for r in rows:
        resolved_agent, _resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )
        ar = by_agent.setdefault(
            resolved_agent,
            AgentTarget(agent_id=resolved_agent, agent_name="", target_pct=target_pct),
        )
        cell = ar.cell(r["month"])
        if r["year"] == year_prev:
            cell.prev_sales += r["amount"]
        elif r["year"] == year_curr:
            cell.curr_sales += r["amount"]

    agent_ids = {aid for aid in by_agent.keys() if aid is not None}
    agent_names = await _hydrate_agent_names(session, tenant_id, agent_ids)
    for aid, ar in by_agent.items():
        ar.agent_name = (
            agent_names.get(aid, "— nemapat —") if aid else "— nemapat —"
        )
        # Asigură existența celor 12 celule
        for m in range(1, 13):
            ar.cell(m)

    def _sort_key(a: AgentTarget) -> tuple[int, Decimal]:
        is_unassigned = 1 if a.agent_id is None else 0
        return (is_unassigned, -a.totals().curr_sales)

    return sorted(by_agent.values(), key=_sort_key)


# ── Public entry-points ──────────────────────────────────────────────────

async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    target_pct: Decimal = DEFAULT_TARGET_PCT,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_ADP,
        target_pct=target_pct,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_ADP for s in g],
    )
    return {
        "scope": "adp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "target_pct": target_pct,
        "last_update": last_update,
        "agents": agents,
    }


async def get_for_sika(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    target_pct: Decimal = DEFAULT_TARGET_PCT,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_SIKA,
        target_pct=target_pct,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKA for s in g],
    )
    return {
        "scope": "sika",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "target_pct": target_pct,
        "last_update": last_update,
        "agents": agents,
    }


async def get_for_sikadp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    target_pct: Decimal = DEFAULT_TARGET_PCT,
) -> dict[str, Any]:
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=_GROUPS_SIKADP,
        target_pct=target_pct,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKADP for s in g],
    )
    return {
        "scope": "sikadp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "target_pct": target_pct,
        "last_update": last_update,
        "agents": agents,
    }
