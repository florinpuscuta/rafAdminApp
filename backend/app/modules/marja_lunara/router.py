from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.margine import service as margine_svc
from app.modules.marja_lunara import service as svc
from app.modules.marja_lunara.schemas import (
    MarjaLunaraResponse,
    MLGroupRow,
    MLMonthRow,
)


router = APIRouter(prefix="/api/marja-lunara", tags=["marja-lunara"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in margine_svc.SCOPE_SOURCES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp', 'sika' sau 'sikadp'",
            },
        )
    return s


def _validate_period(fy: int, fm: int, ty: int, tm: int) -> None:
    if not (1 <= fm <= 12) or not (1 <= tm <= 12):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "month trebuie 1..12"},
        )
    if (fy, fm) > (ty, tm):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_period", "message": "from > to"},
        )


@router.get("", response_model=MarjaLunaraResponse)
async def get_marja_lunara(
    scope: str = Query("adp"),
    from_year: int = Query(..., alias="fromYear"),
    from_month: int = Query(..., alias="fromMonth"),
    to_year: int = Query(..., alias="toYear"),
    to_month: int = Query(..., alias="toMonth"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> MarjaLunaraResponse:
    s = _validate_scope(scope)
    _validate_period(from_year, from_month, to_year, to_month)
    data = await svc.build_marja_lunara(
        session,
        tenant_id=tenant_id,
        scope=s,
        from_year=from_year, from_month=from_month,
        to_year=to_year, to_month=to_month,
    )
    return MarjaLunaraResponse(
        scope=data.scope,
        from_year=data.from_year, from_month=data.from_month,
        to_year=data.to_year, to_month=data.to_month,
        months=[
            MLMonthRow(
                year=m.year, month=m.month,
                revenue_period=m.revenue_period,
                revenue_covered=m.revenue_covered,
                cost_total=m.cost_total,
                profit_total=m.profit_total,
                margin_pct=m.margin_pct,
                discount_total=m.discount_total,
                discount_allocated_total=m.discount_allocated_total,
                profit_net_total=m.profit_net_total,
                margin_pct_net=m.margin_pct_net,
                has_monthly_snapshot=m.has_monthly_snapshot,
                fallback_revenue_pct=m.fallback_revenue_pct,
                products_with_cost=m.products_with_cost,
                products_missing_cost=m.products_missing_cost,
                groups=[
                    MLGroupRow(
                        label=g.label, kind=g.kind, key=g.key,
                        revenue=g.revenue, quantity=g.quantity,
                        cost_total=g.cost_total, profit=g.profit,
                        margin_pct=g.margin_pct,
                        discount_allocated=g.discount_allocated,
                        profit_net=g.profit_net,
                        margin_pct_net=g.margin_pct_net,
                    )
                    for g in m.groups
                ],
            )
            for m in data.months
        ],
    )
