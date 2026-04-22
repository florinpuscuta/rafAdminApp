"""Prognoză Vânzări — forecast KA pe orizont 1..12 luni, per scope.

METODOLOGIE
-----------
Input: vânzări lunare KA (RawSale.amount, channel='KA'), 3 scope-uri cu batch
source scoping identic cu `analiza_pe_luni`:
    - adp    → [["sales_xlsx"]]
    - sika   → [["sika_mtd_xlsx", "sika_xlsx"]]  (MTD are prioritate)
    - sikadp → [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]

Algoritm forecast, per lună viitoare `t+k` (k=1..horizon):
    1. Media mobilă M = medie(ultimele 3 luni complete din istoric).
    2. Factor sezonal S (dacă există date în same-month anul precedent):
          S = sales[t+k-12] / avg(sales[t+k-12-2 .. t+k-12])
       altfel S = 1.
    3. Forecast[t+k] = M * S
    Metoda e "moving_avg_3m_with_seasonal" când S ≠ 1 pe cel puţin o lună,
    altfel "moving_avg_3m".

Linear regression (OLS) pe ultimele 12 luni calculată separat și expusă ca
`trend_pct` pentru transparență în UI — NU se aplică la valoarea forecast
(regression pe serie cu sezonalitate puternică e mai zgomotoasă decât medie
mobilă + sezonal; o afișăm însă pentru că cere specificația).

Ancora: ultima lună completă = luna înainte de luna sistemului (luna curentă
e incompletă, deci o excludem din istoric — identic cu `analiza_pe_luni`).

Rezolvarea (agent_id, store_id) canonică se face via SAM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
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
_MONTH_SHORT = [
    "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
]


def month_name(m: int) -> str:
    return _MONTH_NAMES[m] if 1 <= m <= 12 else ""


def month_short(m: int) -> str:
    return _MONTH_SHORT[m] if 1 <= m <= 12 else ""


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, (total % 12) + 1


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]
_GROUPS_SIKADP: list[list[str]] = [
    ["sales_xlsx"],
    ["sika_mtd_xlsx", "sika_xlsx"],
]


@dataclass
class AgentMonthly:
    agent_id: UUID | None
    agent_name: str
    months: dict[tuple[int, int], Decimal] = field(default_factory=dict)

    def get(self, year: int, month: int) -> Decimal:
        return self.months.get((year, month), Decimal(0))


# ── Data pulling (mirrored pe analiza_pe_luni, dar pe 13 luni inapoi) ─────


async def _sales_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_from: int,
    month_from: int,
    year_to: int,
    month_to: int,
    batch_source_groups: list[list[str]],
) -> list[dict[str, Any]]:
    """Rânduri agregate pe (agent_id, store_id, client, year, month) pentru KA
    în fereastra [year_from,month_from] .. [year_to,month_to] inclusiv.

    Same dedup semantics as analiza_pe_luni: grupurile se însumează, în cadrul
    unui grup prioritatea e pe ordinea listei (primul source cu date pe
    (year, month) câștigă).
    """
    ym_from = year_from * 100 + month_from
    ym_to = year_to * 100 + month_to

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
                    (RawSale.year * 100 + RawSale.month) >= ym_from,
                    (RawSale.year * 100 + RawSale.month) <= ym_to,
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


# ── Forecast math ────────────────────────────────────────────────────────


def _moving_avg_3m(monthly_totals: dict[tuple[int, int], Decimal],
                   anchor_y: int, anchor_m: int) -> Decimal:
    """Media ultimelor 3 luni complete pana la (anchor_y, anchor_m) inclusiv."""
    vals: list[Decimal] = []
    for k in range(3):
        y, m = add_months(anchor_y, anchor_m, -k)
        v = monthly_totals.get((y, m))
        if v is not None and v > 0:
            vals.append(v)
    if not vals:
        return Decimal(0)
    return sum(vals, Decimal(0)) / Decimal(len(vals))


def _seasonal_factor(monthly_totals: dict[tuple[int, int], Decimal],
                     target_y: int, target_m: int) -> Decimal | None:
    """Factor sezonal = sales[target-12] / avg_3m_around(target-12).

    Returnează None dacă lipsesc date pentru estimare robustă.
    """
    py_y, py_m = target_y - 1, target_m
    py_val = monthly_totals.get((py_y, py_m))
    if py_val is None or py_val <= 0:
        return None
    # media 3 luni in jurul target-12 ca baseline (exclude valoarea tinta)
    ref_vals: list[Decimal] = []
    for delta in (-1, 1, -2):  # luna precedenta, urmatoare, 2 luni in urma
        y, m = add_months(py_y, py_m, delta)
        v = monthly_totals.get((y, m))
        if v is not None and v > 0:
            ref_vals.append(v)
        if len(ref_vals) >= 2:
            break
    if len(ref_vals) < 2:
        return None
    baseline = sum(ref_vals, Decimal(0)) / Decimal(len(ref_vals))
    if baseline <= 0:
        return None
    return py_val / baseline


def _linear_trend_pct(monthly_totals: dict[tuple[int, int], Decimal],
                      anchor_y: int, anchor_m: int,
                      lookback: int = 12) -> Decimal | None:
    """OLS slope pe ultimele `lookback` luni, returnat ca % per luna.

    Returnează None dacă < 4 puncte non-zero sau media e 0.
    """
    xs: list[float] = []
    ys: list[float] = []
    for k in range(lookback):
        y, m = add_months(anchor_y, anchor_m, -k)
        v = monthly_totals.get((y, m))
        if v is not None and v > 0:
            xs.append(float(lookback - 1 - k))  # x creste in timp
            ys.append(float(v))
    if len(xs) < 4:
        return None
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    if mean_y == 0:
        return None
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    if den == 0:
        return None
    slope = num / den  # unitati RON per luna
    return Decimal(str(round(slope / mean_y * 100, 2)))


# ── Public entry points ──────────────────────────────────────────────────


async def get_forecast(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    horizon_months: int,
) -> dict[str, Any]:
    """Generează forecast pentru un scope + orizont. Ancora = luna precedenta
    (luna curenta e incompleta)."""
    scope = scope.lower()
    if scope == "adp":
        groups = _GROUPS_ADP
    elif scope == "sika":
        groups = _GROUPS_SIKA
    elif scope == "sikadp":
        groups = _GROUPS_SIKADP
    else:
        raise ValueError(f"invalid scope: {scope}")

    now = datetime.now(timezone.utc)
    # Ancora: luna precedenta lunii sistemului (ultima lună completă)
    anchor_y, anchor_m = add_months(now.year, now.month, -1)

    # Luam fereastra suficient de larga pentru:
    #  - ultimele 12 luni istoric (display + linear regression)
    #  - + inca 12 luni in urma pentru factor sezonal (same-month PY)
    #  = 24 luni inapoi fata de ancora.
    oldest_y, oldest_m = add_months(anchor_y, anchor_m, -23)

    rows = await _sales_rows(
        session, tenant_id,
        year_from=oldest_y, month_from=oldest_m,
        year_to=anchor_y, month_to=anchor_m,
        batch_source_groups=groups,
    )

    # Totaluri lunare (peste toti agentii)
    monthly_totals: dict[tuple[int, int], Decimal] = {}
    # Per agent per luna
    per_agent: dict[UUID | None, AgentMonthly] = {}

    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"]
        for r in rows
        if r["agent_id"] is None and r["store_id"] is not None
    }
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    for r in rows:
        resolved_agent, _resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )
        key = (int(r["year"]), int(r["month"]))
        monthly_totals[key] = monthly_totals.get(key, Decimal(0)) + Decimal(r["amount"])
        am = per_agent.setdefault(
            resolved_agent,
            AgentMonthly(agent_id=resolved_agent, agent_name=""),
        )
        am.months[key] = am.months.get(key, Decimal(0)) + Decimal(r["amount"])

    # Hydrate nume agenti
    agent_ids = {aid for aid in per_agent.keys() if aid is not None}
    agent_names = await _hydrate_agent_names(session, tenant_id, agent_ids)
    for aid, am in per_agent.items():
        am.agent_name = agent_names.get(aid, "— nemapat —") if aid else "— nemapat —"

    last_update = await _last_update(
        session, tenant_id, sources=[s for g in groups for s in g],
    )

    # Istoric pentru display: ultimele 12 luni (in ordine cronologica)
    history_points = []
    any_seasonal_used = False
    for k in range(11, -1, -1):
        y, m = add_months(anchor_y, anchor_m, -k)
        v = monthly_totals.get((y, m), Decimal(0))
        history_points.append({
            "year": y, "month": m,
            "month_name": month_name(m),
            "label": f"{month_short(m)} {y}",
            "sales": v,
        })

    # Forecast pe horizon_months viitor
    forecast_points = []
    for k in range(1, horizon_months + 1):
        ty, tm = add_months(anchor_y, anchor_m, k)
        ma = _moving_avg_3m(monthly_totals, anchor_y, anchor_m)
        sf = _seasonal_factor(monthly_totals, ty, tm)
        if sf is not None:
            any_seasonal_used = True
            forecast = ma * sf
        else:
            forecast = ma
        trend_pct = _linear_trend_pct(monthly_totals, anchor_y, anchor_m, lookback=12)
        forecast_points.append({
            "year": ty, "month": tm,
            "month_name": month_name(tm),
            "label": f"{month_short(tm)} {ty}",
            "forecast_sales": forecast,
            "moving_avg": ma,
            "seasonal_factor": sf,
            "trend_pct": trend_pct,
        })

    # Per-agent: istoric total (ultimele 12 luni) + forecast pe orizont
    # Forecast-ul per-agent = cota agentului din total * forecast total.
    # Rationament: agenții preced patterns globale aproximativ proporțional;
    # distribuirea pe cotă e suficientă pentru o prognoză indicativă.
    agent_rows_out: list[dict[str, Any]] = []
    total_hist_12m = Decimal(0)
    agent_hist_12m: dict[UUID | None, Decimal] = {}
    for aid, am in per_agent.items():
        h = Decimal(0)
        for k in range(12):
            y, m = add_months(anchor_y, anchor_m, -k)
            h += am.get(y, m)
        agent_hist_12m[aid] = h
        total_hist_12m += h

    for aid, am in per_agent.items():
        h = agent_hist_12m[aid]
        share = (h / total_hist_12m) if total_hist_12m > 0 else Decimal(0)
        fc_months: list[Decimal] = []
        fc_total = Decimal(0)
        for fp in forecast_points:
            val = fp["forecast_sales"] * share
            fc_months.append(val)
            fc_total += val
        agent_rows_out.append({
            "agent_id": aid,
            "agent_name": am.agent_name,
            "history_total": h,
            "forecast_total": fc_total,
            "forecast_months": fc_months,
        })

    # Sortare: agenti mapati primii (descrescător după history_total), nemapat la coadă
    def _sort_key(ar: dict[str, Any]) -> tuple[int, Decimal]:
        is_unassigned = 1 if ar["agent_id"] is None else 0
        return (is_unassigned, -ar["history_total"])
    agent_rows_out.sort(key=_sort_key)

    method = "moving_avg_3m_with_seasonal" if any_seasonal_used else "moving_avg_3m"
    last_complete = f"{month_name(anchor_m)} {anchor_y}" if monthly_totals else None

    return {
        "scope": scope,
        "horizon_months": horizon_months,
        "method": method,
        "last_update": last_update,
        "last_complete_month": last_complete,
        "history": history_points,
        "forecast": forecast_points,
        "agents": agent_rows_out,
    }
