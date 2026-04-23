"""
"Bonusări" — calcul bonus lunar per agent, bazat pe creștere YoY.

Reguli legacy, păstrate 1:1 cu adeplast-dashboard:

    growth = (curr - prev) / prev * 100
    bonus tiers (prima regulă match-uită):
        ≥ +15% → 5.500 lei
        ≥ +10% → 3.500 lei
        ≥ +5%  → 2.500 lei
        ≥ +1%  → 2.000 lei
        altfel → 0

    recovery: dacă luna M-1 a ratat (<+1%) dar cumulat prev→M ≥ +1%,
    primești +1.000 lei recovery în luna M.

Luni viitoare (month > current_month pentru anul curent): bonus = 0, nu
declanșează recovery. Luna January fără prev non-zero: 0.

Reutilizează agregarea de vânzări din `targhet.service` (aceleași scope
source-uri, aceeași rezolvare via SAM).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.targhet.service import (
    AgentTarget,
    MonthCell,
    _build_agents,
    _GROUPS_ADP,
    _GROUPS_SIKA,
    _GROUPS_SIKADP,
    _last_update,
    month_name,
)


# ── Reguli bonus (legacy; imutabile decât printr-o schimbare explicită) ──
BONUS_TIERS: list[tuple[Decimal, Decimal]] = [
    (Decimal(15), Decimal(5500)),
    (Decimal(10), Decimal(3500)),
    (Decimal(5), Decimal(2500)),
    (Decimal(1), Decimal(2000)),
]
RECOVERY_AMOUNT: Decimal = Decimal(1000)
RECOVERY_THRESHOLD_PCT: Decimal = Decimal(1)


def calc_bonus(growth_pct: Decimal) -> Decimal:
    for threshold, amount in BONUS_TIERS:
        if growth_pct >= threshold:
            return amount
    return Decimal(0)


def growth_pct(curr: Decimal, prev: Decimal) -> Decimal:
    if prev <= 0:
        return Decimal(100) if curr > 0 else Decimal(0)
    return ((curr - prev) / prev) * Decimal(100)


@dataclass
class BonusMonthResult:
    month: int
    prev_sales: Decimal
    curr_sales: Decimal
    growth_pct: Decimal
    bonus: Decimal
    recovery: Decimal
    is_future: bool

    @property
    def total(self) -> Decimal:
        return self.bonus + self.recovery


@dataclass
class BonusAgentRow:
    agent_id: UUID | None
    agent_name: str
    months: list[BonusMonthResult] = field(default_factory=list)
    total_bonus: Decimal = Decimal(0)

    def recompute_total(self) -> None:
        self.total_bonus = sum((m.total for m in self.months), Decimal(0))


def _build_bonus_for_agent(
    a: AgentTarget, *, year_curr: int, current_month_limit: int,
) -> BonusAgentRow:
    """Rulează logica de recovery peste toate cele 12 luni în ordine cronologică.

    `current_month_limit`: ultima lună "realizabilă" (inclusiv). Lunile >
    acest prag sunt marcate is_future și primesc bonus=0, recovery=0, dar
    nu resetează starea `prev_missed` (nu le folosim în decizii).
    """
    cum_curr = Decimal(0)
    cum_prev = Decimal(0)
    prev_missed = False
    results: list[BonusMonthResult] = []

    for m in range(1, 13):
        cell: MonthCell = a.months.get(m) or MonthCell(month=m)
        is_future = m > current_month_limit

        if is_future or cell.prev_sales <= 0:
            results.append(BonusMonthResult(
                month=m,
                prev_sales=cell.prev_sales,
                curr_sales=cell.curr_sales,
                growth_pct=Decimal(0),
                bonus=Decimal(0),
                recovery=Decimal(0),
                is_future=is_future,
            ))
            # Dacă prev e 0 și luna nu e viitoare, o tratăm ca ratată
            if not is_future and cell.prev_sales <= 0:
                cum_curr += cell.curr_sales
                cum_prev += cell.prev_sales
                prev_missed = True
            continue

        cum_curr += cell.curr_sales
        cum_prev += cell.prev_sales

        g = growth_pct(cell.curr_sales, cell.prev_sales)
        bonus = calc_bonus(g)
        recovery = Decimal(0)
        if prev_missed and m > 1:
            cum_g = growth_pct(cum_curr, cum_prev)
            if cum_g >= RECOVERY_THRESHOLD_PCT:
                recovery = RECOVERY_AMOUNT

        results.append(BonusMonthResult(
            month=m,
            prev_sales=cell.prev_sales,
            curr_sales=cell.curr_sales,
            growth_pct=g,
            bonus=bonus,
            recovery=recovery,
            is_future=False,
        ))
        prev_missed = (g < RECOVERY_THRESHOLD_PCT)

    row = BonusAgentRow(
        agent_id=a.agent_id,
        agent_name=a.agent_name,
        months=results,
    )
    row.recompute_total()
    return row


async def _compute(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    month: int | None,
    batch_source_groups: list[list[str]],
) -> dict[str, Any]:
    """Ia agenții + celule lunare și aplică regulile de bonus."""
    agents = await _build_agents(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        pct_by_month={m: Decimal(0) for m in range(1, 13)},  # nu influențează bonus
    )

    now = datetime.now(timezone.utc)
    if month is not None:
        current_month_limit = month
    elif year_curr == now.year:
        current_month_limit = now.month
    else:
        current_month_limit = 12

    rows = [
        _build_bonus_for_agent(
            a, year_curr=year_curr, current_month_limit=current_month_limit,
        )
        for a in agents
    ]
    rows.sort(key=lambda r: (-r.total_bonus, r.agent_name.lower()))

    last_update = await _last_update(
        session, tenant_id, sources=[s for g in batch_source_groups for s in g],
    )
    return {
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "current_month_limit": current_month_limit,
        "last_update": last_update,
        "agents": rows,
    }


# ── Public entry-points ──────────────────────────────────────────────────

async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, month: int | None,
) -> dict[str, Any]:
    data = await _compute(
        session, tenant_id, year_curr=year_curr, month=month,
        batch_source_groups=_GROUPS_ADP,
    )
    return {"scope": "adp", **data}


async def get_for_sika(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, month: int | None,
) -> dict[str, Any]:
    data = await _compute(
        session, tenant_id, year_curr=year_curr, month=month,
        batch_source_groups=_GROUPS_SIKA,
    )
    return {"scope": "sika", **data}


async def get_for_sikadp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, month: int | None,
) -> dict[str, Any]:
    data = await _compute(
        session, tenant_id, year_curr=year_curr, month=month,
        batch_source_groups=_GROUPS_SIKADP,
    )
    return {"scope": "sikadp", **data}


# Re-export helper pentru router
__all__ = [
    "BONUS_TIERS",
    "RECOVERY_AMOUNT",
    "RECOVERY_THRESHOLD_PCT",
    "BonusAgentRow",
    "BonusMonthResult",
    "get_for_adp",
    "get_for_sika",
    "get_for_sikadp",
    "month_name",
]
