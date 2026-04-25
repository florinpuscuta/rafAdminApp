from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.margine import service as svc
from app.modules.margine.schemas import (
    MargineGroupRow,
    MargineMissingRow,
    MargineProductRow,
    MargineResponse,
)


router = APIRouter(prefix="/api/margine", tags=["margine"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in svc.SCOPE_SOURCES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp', 'sika' sau 'sikadp'",
            },
        )
    return s


def _validate_period(
    from_year: int, from_month: int, to_year: int, to_month: int,
) -> None:
    if not (1 <= from_month <= 12) or not (1 <= to_month <= 12):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "month trebuie 1..12"},
        )
    if (from_year, from_month) > (to_year, to_month):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_period", "message": "from > to"},
        )


@router.get("", response_model=MargineResponse)
async def get_margine(
    scope: str = Query("adp"),
    from_year: int = Query(..., alias="fromYear"),
    from_month: int = Query(..., alias="fromMonth"),
    to_year: int = Query(..., alias="toYear"),
    to_month: int = Query(..., alias="toMonth"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> MargineResponse:
    s = _validate_scope(scope)
    _validate_period(from_year, from_month, to_year, to_month)
    data = await svc.build_margine(
        session,
        tenant_id=tenant_id,
        scope=s,
        from_year=from_year, from_month=from_month,
        to_year=to_year, to_month=to_month,
    )
    return MargineResponse(
        scope=data.scope,
        from_year=data.from_year, from_month=data.from_month,
        to_year=data.to_year, to_month=data.to_month,
        revenue_period=data.revenue_period,
        revenue_covered=data.revenue_covered,
        cost_total=data.cost_total,
        profit_total=data.profit_total,
        margin_pct=data.margin_pct,
        coverage_pct=data.coverage_pct,
        discount_total=data.discount_total,
        discount_allocated_total=data.discount_allocated_total,
        profit_net_total=data.profit_net_total,
        margin_pct_net=data.margin_pct_net,
        products_with_cost=data.products_with_cost,
        products_missing_cost=data.products_missing_cost,
        groups=[
            MargineGroupRow(
                label=g.label, kind=g.kind, key=g.key,
                revenue=g.revenue, quantity=g.quantity,
                cost_total=g.cost_total, profit=g.profit,
                margin_pct=g.margin_pct,
                discount_allocated=g.discount_allocated,
                profit_net=g.profit_net,
                margin_pct_net=g.margin_pct_net,
                products=[
                    MargineProductRow(
                        product_id=p.product_id,
                        product_code=p.product_code,
                        product_name=p.product_name,
                        revenue=p.revenue, quantity=p.quantity,
                        avg_sale=p.avg_sale, cost=p.cost,  # type: ignore[arg-type]
                        profit=p.profit,  # type: ignore[arg-type]
                        margin_pct=p.margin_pct,  # type: ignore[arg-type]
                    )
                    for p in g.products
                ],
            )
            for g in data.groups
        ],
        missing_cost=[
            MargineMissingRow(
                product_id=m.product_id,
                product_code=m.product_code,
                product_name=m.product_name,
                revenue=m.revenue,
                quantity=m.quantity,
            )
            for m in data.missing_cost
        ],
    )
