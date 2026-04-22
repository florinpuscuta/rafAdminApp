"""
Agregări "Consolidat KA" — Y1 vs Y2 pe channel KA, filtrat pe scope-ul
companiei (adeplast / sika / sikadp).

Scope via `ImportBatch.source`:
  - adeplast → batch.source = 'sales_xlsx'
  - sika     → batch.source IN ('sika_mtd_xlsx', 'sika_xlsx') — dedup per
               (year, month) pe prioritatea MTD > historical
  - sikadp   → uniune ADP + SIKA (după rezolvarea agent/store)

Rezolvare agent/store canonic via SAM (vezi `mappings.resolution`). Numerele
și agenții/magazinele reflectă asignarea curentă din SAM, nu raw_sales.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
from app.modules.sales.models import ImportBatch, RawSale


_MONTH_LABELS_SHORT = [
    "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
]


def _company_label(company: str) -> str:
    c = company.lower()
    if c == "adeplast":
        return "Adeplast KA"
    if c == "sika":
        return "Sika KA"
    if c == "sikadp":
        return "SikaDP KA"
    return f"{company} KA"


def build_period_label(months: list[int]) -> str:
    if not months:
        return ""
    sorted_m = sorted(set(months))
    start = _MONTH_LABELS_SHORT[sorted_m[0]]
    end = _MONTH_LABELS_SHORT[sorted_m[-1]]
    if start == end:
        return f"YTD — {start}"
    return f"YTD — {start} → {end}"


def pct_change(y1: Decimal, y2: Decimal) -> float:
    if y1 == 0:
        return 0.0
    return float((y2 - y1) / y1 * 100)


# ── Scope → batch sources (ordonat pe prioritate) ──────────────────────────

def _scope_sources(company: str) -> list[list[str]]:
    """Returnează grupuri de batch_sources per scope.

    Fiecare grup e ordonat pe PRIORITATE — per (year, month) se folosește doar
    primul source cu date. Grupuri separate = nu se aplică dedup între ele.

    adeplast → [['sales_xlsx']]
    sika     → [['sika_mtd_xlsx', 'sika_xlsx']]  (dedup MTD > historical)
    sikadp   → [['sales_xlsx'], ['sika_mtd_xlsx', 'sika_xlsx']]
    """
    c = company.lower()
    if c == "adeplast":
        return [["sales_xlsx"]]
    if c == "sika":
        return [["sika_mtd_xlsx", "sika_xlsx"]]
    if c == "sikadp":
        return [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]
    return []


# ── Core: fetch raw rows (cu dedup per source-group) ───────────────────────

async def _fetch_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str,
    y1: int,
    y2: int,
    months: list[int],
) -> list[dict[str, Any]]:
    """Returnează rânduri agregate pe (agent_id, store_id, client) cu
    sales_y1 și sales_y2, aplicând dedup între sika_xlsx și sika_mtd_xlsx
    (per grup de priority sources).
    """
    groups = _scope_sources(company)
    if not groups or not months:
        return []

    sales_y1 = func.coalesce(
        func.sum(case((RawSale.year == y1, RawSale.amount), else_=0)), 0
    )
    sales_y2 = func.coalesce(
        func.sum(case((RawSale.year == y2, RawSale.amount), else_=0)), 0
    )

    # Acumulator: (agent_id, store_id, client) → {sales_y1, sales_y2}
    acc: dict[tuple[UUID | None, UUID | None, str | None], dict[str, Any]] = {}

    for group in groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([y1, y2]),
                    RawSale.month.in_(months),
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
                    sales_y1.label("sales_y1"),
                    sales_y2.label("sales_y2"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .group_by(RawSale.agent_id, RawSale.store_id, RawSale.client)
            )
            result = await session.execute(stmt)
            for r in result.all():
                key = (r.agent_id, r.store_id, r.client)
                row = acc.setdefault(key, {
                    "agent_id": r.agent_id,
                    "store_id": r.store_id,
                    "client": r.client,
                    "sales_y1": Decimal(0),
                    "sales_y2": Decimal(0),
                })
                row["sales_y1"] += Decimal(r.sales_y1 or 0)
                row["sales_y2"] += Decimal(r.sales_y2 or 0)

            claimed_pairs |= new_pairs

    return list(acc.values())


# ── Aggregare cu rezolvare SAM ─────────────────────────────────────────────

async def _resolved_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str,
    y1: int,
    y2: int,
    months: list[int],
) -> list[dict[str, Any]]:
    """Fetch + rezolvă (agent, store) canonic per rând. Returnează
    [{agent_id, store_id, sales_y1, sales_y2}] agregat pe (agent_id, store_id).
    """
    raw = await _fetch_rows(
        session, tenant_id, company=company, y1=y1, y2=y2, months=months,
    )
    if not raw:
        return []

    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"] for r in raw
        if r["agent_id"] is None and r["store_id"] is not None
    }
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    out: dict[tuple[UUID | None, UUID | None], dict[str, Any]] = {}
    for r in raw:
        final_agent, final_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r["client"],
            client_map=client_map, store_map=store_map,
        )
        key = (final_agent, final_store)
        agg = out.setdefault(key, {
            "agent_id": final_agent,
            "store_id": final_store,
            "sales_y1": Decimal(0),
            "sales_y2": Decimal(0),
        })
        agg["sales_y1"] += r["sales_y1"]
        agg["sales_y2"] += r["sales_y2"]
    return list(out.values())


# ── Public API ─────────────────────────────────────────────────────────────

async def totals_for_company(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str,
    y1: int,
    y2: int,
    months: list[int],
) -> dict[str, Decimal]:
    rows = await _resolved_rows(
        session, tenant_id, company=company, y1=y1, y2=y2, months=months,
    )
    total_y1 = sum((r["sales_y1"] for r in rows), Decimal(0))
    total_y2 = sum((r["sales_y2"] for r in rows), Decimal(0))
    return {"sales_y1": total_y1, "sales_y2": total_y2}


async def by_agent(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str,
    y1: int,
    y2: int,
    months: list[int],
) -> list[dict[str, Any]]:
    rows = await _resolved_rows(
        session, tenant_id, company=company, y1=y1, y2=y2, months=months,
    )
    by_agent_acc: dict[UUID | None, dict[str, Any]] = {}
    for r in rows:
        aid = r["agent_id"]
        agg = by_agent_acc.setdefault(aid, {
            "agent_id": aid,
            "stores": set(),
            "sales_y1": Decimal(0),
            "sales_y2": Decimal(0),
        })
        if r["store_id"] is not None:
            agg["stores"].add(r["store_id"])
        agg["sales_y1"] += r["sales_y1"]
        agg["sales_y2"] += r["sales_y2"]

    out = [
        {
            "agent_id": v["agent_id"],
            "stores_count": len(v["stores"]),
            "sales_y1": v["sales_y1"],
            "sales_y2": v["sales_y2"],
        }
        for v in by_agent_acc.values()
    ]
    out.sort(key=lambda r: r["sales_y2"], reverse=True)
    return out


async def by_store_per_agent(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str,
    y1: int,
    y2: int,
    months: list[int],
    agent_id: UUID | None,
) -> list[dict[str, Any]]:
    """Defalcare magazine pentru un agent (sau `None` = nemapate)."""
    rows = await _resolved_rows(
        session, tenant_id, company=company, y1=y1, y2=y2, months=months,
    )
    by_store: dict[UUID | None, dict[str, Any]] = {}
    for r in rows:
        if r["agent_id"] != agent_id:
            continue
        sid = r["store_id"]
        agg = by_store.setdefault(sid, {
            "store_id": sid,
            "sales_y1": Decimal(0),
            "sales_y2": Decimal(0),
        })
        agg["sales_y1"] += r["sales_y1"]
        agg["sales_y2"] += r["sales_y2"]

    out = list(by_store.values())
    out.sort(key=lambda r: r["sales_y2"], reverse=True)
    return out
