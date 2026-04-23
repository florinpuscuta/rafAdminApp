from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.marca_privata import service as svc
from app.modules.marca_privata.schemas import (
    MPCategoryCell,
    MPChainRow,
    MPMonthCell,
    MPResponse,
    MPYearTotals,
)

router = APIRouter(prefix="/api/marca-privata", tags=["marca-privata"])

_SCOPES = {"adp"}


def _pct(y1: Decimal, diff: Decimal) -> Decimal | None:
    return (diff / y1 * Decimal(100)) if y1 != 0 else None


def _month_to_model(c: svc.MonthCell) -> MPMonthCell:
    return MPMonthCell(
        month=c.month,
        month_name=svc.month_name(c.month),
        sales_y1=c.sales_y1,
        sales_y2=c.sales_y2,
        diff=c.diff,
        pct=c.pct,
    )


def _chain_to_model(c: svc.ChainRow) -> MPChainRow:
    # Asigurăm că fiecare rețea returnează toate cele 3 categorii (MU/EPS/UMEDE)
    # în aceeași ordine — chiar dacă una e 0 — ca UI-ul să poată alinia
    # coloanele și plăcintele fără să verifice prezența.
    cats: list[MPCategoryCell] = []
    for code, label in svc.CHAIN_CATEGORIES:
        cell = c.categories.get(code) or svc.CategoryCell(code=code, label=label)
        cats.append(MPCategoryCell(
            code=cell.code,
            label=cell.label,
            sales_y1=cell.sales_y1,
            sales_y2=cell.sales_y2,
            diff=cell.diff,
            pct=cell.pct,
        ))
    return MPChainRow(
        chain=c.chain,
        sales_y1=c.sales_y1,
        sales_y2=c.sales_y2,
        diff=c.diff,
        pct=c.pct,
        categories=cats,
    )


def _build_response(data: svc.MarcaPrivataData) -> MPResponse:
    months = [_month_to_model(data.months[m]) for m in range(1, 13)]
    chains = [_chain_to_model(c) for c in data.chains]

    grand_y1 = sum((m.sales_y1 for m in months), Decimal(0))
    grand_y2 = sum((m.sales_y2 for m in months), Decimal(0))
    grand_diff = grand_y2 - grand_y1

    return MPResponse(
        scope=data.scope,
        year_curr=data.year_curr,
        year_prev=data.year_prev,
        last_update=data.last_update,
        months=months,
        chains=chains,
        grand_totals=MPYearTotals(
            sales_y1=grand_y1,
            sales_y2=grand_y2,
            diff=grand_diff,
            pct=_pct(grand_y1, grand_diff),
        ),
    )


@router.get("", response_model=MPResponse)
async def get_marca_privata(
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
                "message": "scope trebuie 'adp' (marca privată e doar pe Adeplast)",
            },
        )

    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr)
    return _build_response(data)
