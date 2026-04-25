from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.eps import service as eps_service
from app.modules.eps.schemas import (
    EpsBreakdownResponse, EpsClassRow, EpsDetailsResponse, EpsMonthlyRow,
)

router = APIRouter(prefix="/api/eps", tags=["eps"])


def _parse_months(value: str | None) -> list[int] | None:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    months: list[int] = []
    for p in parts:
        try:
            m = int(p)
        except ValueError:
            continue
        if 1 <= m <= 12:
            months.append(m)
    return months or None


@router.get("/details", response_model=EpsDetailsResponse)
async def eps_details(
    y1: int = Query(..., ge=2000, le=2100),
    y2: int = Query(..., ge=2000, le=2100),
    months: str | None = Query(
        None,
        description="CSV de luni 1..12, ex: '1,2,3'. Gol = toate lunile.",
    ),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    if y1 == y2:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_years", "message": "y1 și y2 trebuie să difere"},
        )
    months_list = _parse_months(months)
    rows = await eps_service.details_by_month_by_tenants(
        session, org_ids, y1=y1, y2=y2, months=months_list
    )
    return EpsDetailsResponse(
        y1=y1,
        y2=y2,
        rows=[EpsMonthlyRow(**r) for r in rows],
    )


@router.get("/breakdown", response_model=EpsBreakdownResponse)
async def eps_breakdown(
    y1: int = Query(..., ge=2000, le=2100),
    y2: int = Query(..., ge=2000, le=2100),
    months: str | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """Breakdown EPS KA pe clase (50/70/80/100/120/150/200) — plăci only."""
    if y1 == y2:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_years", "message": "y1 și y2 trebuie să difere"},
        )
    months_list = _parse_months(months)
    rows = await eps_service.breakdown_by_class_by_tenants(
        session, org_ids, y1=y1, y2=y2, months=months_list,
    )
    return EpsBreakdownResponse(
        y1=y1, y2=y2,
        rows=[EpsClassRow(**r) for r in rows],
    )
