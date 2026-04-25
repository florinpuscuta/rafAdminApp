"""
Router /api/probleme — probleme în activitate per lună.

Frontend-ul folosește ruta /probleme/:period unde period = "YYYY-MM".
Backend-ul acceptă fie ?period=YYYY-MM, fie ?year=&month=.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids, get_current_tenant_id, get_current_user
from app.modules.probleme import service as svc
from app.modules.probleme.schemas import ProblemeResponse, ProblemeSaveRequest
from app.modules.users.models import User

router = APIRouter(prefix="/api/probleme", tags=["probleme"])

_SCOPES = {"adp", "sika", "sikadp"}


def _parse_period(period: str | None, year: int | None, month: int | None) -> tuple[int, int]:
    if period:
        try:
            parts = period.split("-")
            if len(parts) != 2:
                raise ValueError
            y, m = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_period", "message": "period trebuie YYYY-MM"},
            )
    else:
        now = datetime.now(timezone.utc)
        y = year or now.year
        m = month or now.month
    if not (1 <= m <= 12):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "luna trebuie 1..12"},
        )
    return y, m


def _check_scope(scope: str) -> str:
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )
    return scope


@router.get("", response_model=ProblemeResponse)
async def get_probleme(
    period: str | None = Query(None, description="YYYY-MM"),
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    scope: str = Query("adp"),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(scope)
    y, m = _parse_period(period, year, month)
    data = await svc.get_probleme_by_tenants(
        session, org_ids, scope=scope, year=y, month=m,
    )
    return ProblemeResponse(**data)


@router.post("", response_model=ProblemeResponse)
async def save_probleme(
    payload: ProblemeSaveRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(payload.scope)
    data = await svc.save_probleme(
        session,
        tenant_id,
        scope=scope,
        year=payload.year,
        month=payload.month,
        content=payload.content,
        updated_by=user.email,
        updated_by_user_id=user.id,
    )
    return ProblemeResponse(**data)
