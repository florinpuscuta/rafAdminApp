from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.analiza_pe_luni import service as svc
from app.modules.analiza_pe_luni.schemas import (
    ApLAgentRow,
    ApLMonthCell,
    ApLMonthTotal,
    ApLResponse,
    ApLYearTotals,
)
from app.modules.auth.deps import get_current_org_ids

router = APIRouter(prefix="/api/analiza-pe-luni", tags=["analiza-pe-luni"])

_SCOPES = {"adp", "sika", "sikadp"}


def _pct(y1: Decimal, diff: Decimal) -> Decimal | None:
    return (diff / y1 * Decimal(100)) if y1 != 0 else None


def _month_cell_to_model(c: svc.AgentMonthCell) -> ApLMonthCell:
    return ApLMonthCell(
        month=c.month,
        month_name=svc.month_name(c.month),
        sales_y1=c.sales_y1,
        sales_y2=c.sales_y2,
        diff=c.diff,
        pct=c.pct,
    )


def _agent_to_model(a: svc.AgentMonthly) -> ApLAgentRow:
    months = [_month_cell_to_model(a.months[m]) for m in range(1, 13)]
    t = a.totals()
    return ApLAgentRow(
        agent_id=a.agent_id,
        agent_name=a.agent_name,
        months=months,
        totals=ApLYearTotals(
            sales_y1=t.sales_y1, sales_y2=t.sales_y2, diff=t.diff, pct=t.pct,
        ),
    )


def _build_response(scope: str, data: dict) -> ApLResponse:
    agent_rows = [_agent_to_model(a) for a in data["agents"]]

    # Totaluri per lună (peste toți agenții)
    per_month_y1: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    per_month_y2: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    for ar in agent_rows:
        for mc in ar.months:
            per_month_y1[mc.month] += mc.sales_y1
            per_month_y2[mc.month] += mc.sales_y2

    month_totals: list[ApLMonthTotal] = []
    for m in range(1, 13):
        y1 = per_month_y1[m]
        y2 = per_month_y2[m]
        diff = y2 - y1
        month_totals.append(
            ApLMonthTotal(
                month=m, month_name=svc.month_name(m),
                sales_y1=y1, sales_y2=y2, diff=diff, pct=_pct(y1, diff),
            )
        )

    grand_y1 = sum((t.sales_y1 for t in month_totals), Decimal(0))
    grand_y2 = sum((t.sales_y2 for t in month_totals), Decimal(0))
    grand_diff = grand_y2 - grand_y1

    return ApLResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        last_update=data["last_update"],
        agents=agent_rows,
        month_totals=month_totals,
        grand_totals=ApLYearTotals(
            sales_y1=grand_y1, sales_y2=grand_y2, diff=grand_diff,
            pct=_pct(grand_y1, grand_diff),
        ),
    )


@router.get("", response_model=ApLResponse)
async def get_analiza_pe_luni(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, ge=2000, le=2100),
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

    async def _fetch_one(tid: UUID) -> dict:
        if scope == "adp":
            return await svc.get_for_adp(session, tid, year_curr=year_curr)
        if scope == "sika":
            return await svc.get_for_sika(session, tid, year_curr=year_curr)
        return await svc.get_for_sikadp(session, tid, year_curr=year_curr)

    parts = [await _fetch_one(tid) for tid in org_ids]
    if len(parts) == 1:
        return _build_response(scope, parts[0])

    # Merge: agentii cu acelasi nume insumati cross-org. AgentMonthCell are
    # diff/pct ca property-uri calculate, deci doar sales_y1/sales_y2 se
    # modifica direct.
    by_name: dict[str, svc.AgentMonthly] = {}
    last_update = None
    for p in parts:
        if p.get("last_update") is not None:
            if last_update is None or p["last_update"] > last_update:
                last_update = p["last_update"]
        for a in p["agents"]:
            existing = by_name.get(a.agent_name)
            if existing is None:
                by_name[a.agent_name] = a
            else:
                for m in range(1, 13):
                    existing.months[m].sales_y1 += a.months[m].sales_y1
                    existing.months[m].sales_y2 += a.months[m].sales_y2

    merged = {
        "year_curr": parts[0]["year_curr"],
        "year_prev": parts[0]["year_prev"],
        "last_update": last_update,
        "agents": sorted(
            by_name.values(),
            key=lambda a: a.totals().sales_y2,
            reverse=True,
        ),
    }
    return _build_response(scope, merged)
