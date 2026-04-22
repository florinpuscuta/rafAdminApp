from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.targhet import service as svc
from app.modules.targhet.schemas import (
    TgtAgentRow,
    TgtMonthCell,
    TgtMonthTotal,
    TgtResponse,
    TgtTotals,
)

router = APIRouter(prefix="/api/targhet", tags=["targhet"])

_SCOPES = {"adp", "sika", "sikadp"}


def _achievement_pct(curr: Decimal, target: Decimal) -> Decimal | None:
    if target == 0:
        return None
    return (curr / target) * Decimal(100)


def _month_cell_to_model(c: svc.MonthCell) -> TgtMonthCell:
    return TgtMonthCell(
        month=c.month,
        month_name=svc.month_name(c.month),
        prev_sales=c.prev_sales,
        curr_sales=c.curr_sales,
        target=c.target,
        gap=c.gap,
        achievement_pct=c.achievement_pct,
    )


def _agent_to_model(a: svc.AgentTarget) -> TgtAgentRow:
    months = [_month_cell_to_model(a.months[m]) for m in range(1, 13)]
    t = a.totals()
    return TgtAgentRow(
        agent_id=a.agent_id,
        agent_name=a.agent_name,
        months=months,
        totals=TgtTotals(
            prev_sales=t.prev_sales,
            curr_sales=t.curr_sales,
            target=t.target,
            gap=t.gap,
            achievement_pct=t.achievement_pct,
        ),
    )


def _build_response(scope: str, data: dict) -> TgtResponse:
    agent_rows = [_agent_to_model(a) for a in data["agents"]]
    target_pct: Decimal = data["target_pct"]

    # Totaluri per lună (peste toți agenții)
    per_month_prev: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    per_month_curr: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    for ar in agent_rows:
        for mc in ar.months:
            per_month_prev[mc.month] += mc.prev_sales
            per_month_curr[mc.month] += mc.curr_sales

    multiplier = (Decimal(100) + target_pct) / Decimal(100)
    month_totals: list[TgtMonthTotal] = []
    for m in range(1, 13):
        prev = per_month_prev[m]
        curr = per_month_curr[m]
        target = prev * multiplier
        gap = curr - target
        month_totals.append(
            TgtMonthTotal(
                month=m,
                month_name=svc.month_name(m),
                prev_sales=prev,
                curr_sales=curr,
                target=target,
                gap=gap,
                achievement_pct=_achievement_pct(curr, target),
            )
        )

    grand_prev = sum((t.prev_sales for t in month_totals), Decimal(0))
    grand_curr = sum((t.curr_sales for t in month_totals), Decimal(0))
    grand_target = grand_prev * multiplier
    grand_gap = grand_curr - grand_target

    return TgtResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        target_pct=target_pct,
        last_update=data["last_update"],
        agents=agent_rows,
        month_totals=month_totals,
        grand_totals=TgtTotals(
            prev_sales=grand_prev,
            curr_sales=grand_curr,
            target=grand_target,
            gap=grand_gap,
            achievement_pct=_achievement_pct(grand_curr, grand_target),
        ),
    )


@router.get("", response_model=TgtResponse)
async def get_targhet(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(
        None, ge=1, le=12,
        description="Acceptat pentru paritate cu celelalte endpoint-uri; "
                    "targhetul întotdeauna returnează cele 12 luni.",
    ),
    target_pct: float | None = Query(
        None, ge=-50, le=500,
        description="Procent creștere față de an precedent. Default: 10.",
    ),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )

    now = datetime.now(timezone.utc)
    year_curr = year or now.year
    # `month` e acceptat pentru API parity (vz_la_zi îl folosește), însă
    # targhetul arată toate cele 12 luni.
    _ = month

    pct = Decimal(str(target_pct)) if target_pct is not None else svc.DEFAULT_TARGET_PCT

    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr, target_pct=pct)
    elif scope == "sika":
        data = await svc.get_for_sika(session, tenant_id, year_curr=year_curr, target_pct=pct)
    else:
        data = await svc.get_for_sikadp(session, tenant_id, year_curr=year_curr, target_pct=pct)

    return _build_response(scope, data)
