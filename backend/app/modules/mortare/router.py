from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.mortare import service as svc
from app.modules.mortare.schemas import (
    MortareMonthCell,
    MortareProductRow,
    MortareResponse,
    MortareYearTotals,
)

router = APIRouter(prefix="/api/mortare", tags=["mortare"])

_SCOPES = {"adp"}


def _pct(y1: Decimal, diff: Decimal) -> Decimal | None:
    return (diff / y1 * Decimal(100)) if y1 != 0 else None


def _month_to_model(c: svc.MonthCell) -> MortareMonthCell:
    return MortareMonthCell(
        month=c.month,
        month_name=svc.month_name(c.month),
        sales_y1=c.sales_y1,
        sales_y2=c.sales_y2,
        qty_y1=c.qty_y1,
        qty_y2=c.qty_y2,
        diff=c.diff,
        pct=c.pct,
    )


def _product_to_model(p: svc.ProductRow) -> MortareProductRow:
    return MortareProductRow(
        product_id=p.product_id,
        product_code=p.product_code,
        product_name=p.product_name,
        sales_y1=p.sales_y1,
        sales_y2=p.sales_y2,
        qty_y1=p.qty_y1,
        qty_y2=p.qty_y2,
        diff=p.diff,
        pct=p.pct,
    )


def _build_response(data: svc.MortareData) -> MortareResponse:
    months = [_month_to_model(data.months[m]) for m in range(1, 13)]
    products = [_product_to_model(p) for p in data.products]

    grand_y1 = sum((m.sales_y1 for m in months), Decimal(0))
    grand_y2 = sum((m.sales_y2 for m in months), Decimal(0))
    qy1 = sum((m.qty_y1 for m in months), Decimal(0))
    qy2 = sum((m.qty_y2 for m in months), Decimal(0))
    grand_diff = grand_y2 - grand_y1

    return MortareResponse(
        scope=data.scope,
        year_curr=data.year_curr,
        year_prev=data.year_prev,
        last_update=data.last_update,
        months=months,
        products=products,
        grand_totals=MortareYearTotals(
            sales_y1=grand_y1,
            sales_y2=grand_y2,
            qty_y1=qy1,
            qty_y2=qy2,
            diff=grand_diff,
            pct=_pct(grand_y1, grand_diff),
        ),
    )


@router.get("", response_model=MortareResponse)
async def get_mortare(
    scope: str = Query("adp", description="'adp' (momentan doar ADP)"),
    year: int | None = Query(None, ge=2000, le=2100),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp' (mortarele silozuri sunt doar pe Adeplast)",
            },
        )

    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr)
    return _build_response(data)
