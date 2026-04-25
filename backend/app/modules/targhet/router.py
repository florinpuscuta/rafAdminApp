from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids, get_current_tenant_id
from app.modules.targhet import service as svc
from app.modules.targhet.schemas import (
    TgtAgentRow,
    TgtGrowthItem,
    TgtGrowthList,
    TgtGrowthUpsert,
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
        target_pct=c.target_pct,
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
    pct_by_month: dict[int, Decimal] = data["pct_by_month"]

    per_month_prev: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    per_month_curr: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    for ar in agent_rows:
        for mc in ar.months:
            per_month_prev[mc.month] += mc.prev_sales
            per_month_curr[mc.month] += mc.curr_sales

    month_totals: list[TgtMonthTotal] = []
    grand_prev = Decimal(0)
    grand_curr = Decimal(0)
    grand_target = Decimal(0)
    for m in range(1, 13):
        prev = per_month_prev[m]
        curr = per_month_curr[m]
        pct = pct_by_month.get(m, svc.DEFAULT_TARGET_PCT)
        target = prev * (Decimal(100) + pct) / Decimal(100)
        gap = curr - target
        month_totals.append(
            TgtMonthTotal(
                month=m,
                month_name=svc.month_name(m),
                prev_sales=prev,
                curr_sales=curr,
                target=target,
                target_pct=pct,
                gap=gap,
                achievement_pct=_achievement_pct(curr, target),
            )
        )
        grand_prev += prev
        grand_curr += curr
        grand_target += target

    growth_list = [
        TgtGrowthItem(year=data["year_curr"], month=m, pct=pct_by_month.get(m, svc.DEFAULT_TARGET_PCT))
        for m in range(1, 13)
    ]

    return TgtResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        last_update=data["last_update"],
        agents=agent_rows,
        month_totals=month_totals,
        grand_totals=TgtTotals(
            prev_sales=grand_prev,
            curr_sales=grand_curr,
            target=grand_target,
            gap=grand_curr - grand_target,
            achievement_pct=_achievement_pct(grand_curr, grand_target),
        ),
        growth_pct=growth_list,
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
    tenant_id: UUID = Depends(get_current_tenant_id),
    org_ids: list[UUID] = Depends(get_current_org_ids),
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
    _ = month

    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr)
    elif scope == "sika":
        data = await svc.get_for_sika(session, tenant_id, year_curr=year_curr)
    else:
        data = await svc.get_for_sikadp_merged(
            session, org_ids, year_curr=year_curr,
        )

    return _build_response(scope, data)


@router.get("/growth-pct", response_model=TgtGrowthList)
async def get_growth_pct(
    year: int = Query(..., ge=2000, le=2100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    m = await svc.load_growth_pct_map(session, tenant_id, year=year)
    return TgtGrowthList(
        year=year,
        items=[TgtGrowthItem(year=year, month=mo, pct=m[mo]) for mo in range(1, 13)],
    )


@router.put("/growth-pct", response_model=TgtGrowthList)
async def put_growth_pct(
    payload: TgtGrowthUpsert,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """Pe SIKADP propagă pct la toate org_ids ca să fie sincronizate
    (zona-agent calculează target per-tenant cu pct-ul propriu)."""
    items = [(it.month, it.pct) for it in payload.items]
    m = await svc.upsert_growth_pct_multi(
        session, org_ids, year=payload.year, items=items,
    )
    await session.commit()
    return TgtGrowthList(
        year=payload.year,
        items=[TgtGrowthItem(year=payload.year, month=mo, pct=m[mo]) for mo in range(1, 13)],
    )
