"""
Router pentru /api/activitate.

GET /api/activitate:
  ?scope=adp|sika|sikadp  (pentru consistență cu vz-la-zi)
  ?date=YYYY-MM-DD        (o singură zi)
  ?from=...&to=...        (interval)

POST /api/activitate/visits: adaugă o vizită nouă (CRUD minim).
"""
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.activitate import service as svc
from app.modules.activitate.schemas import (
    ActivitateResponse,
    ActivitateVisitCreate,
    ActivitateVisitCreated,
)
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/api/activitate", tags=["activitate"])

_SCOPES = {"adp", "sika", "sikadp"}


def _check_scope(scope: str) -> str:
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )
    return scope


@router.get("", response_model=ActivitateResponse)
async def get_activitate(
    scope: str = Query("adp"),
    date_: date | None = Query(None, alias="date"),
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(scope)

    today = datetime.now(timezone.utc).date()
    if date_ is not None:
        df = dt = date_
    else:
        df = date_from or today
        dt = date_to or df
    if dt < df:
        df, dt = dt, df

    data = await svc.get_activitate(
        session, tenant_id, scope=scope, date_from=df, date_to=dt,
    )
    return ActivitateResponse(**data)


@router.post("/visits", response_model=ActivitateVisitCreated, status_code=status.HTTP_201_CREATED)
async def create_visit(
    payload: ActivitateVisitCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(payload.scope)
    visit = await svc.create_visit(
        session,
        tenant_id,
        scope=scope,
        visit_date=payload.visit_date,
        agent_id=payload.agent_id,
        store_id=payload.store_id,
        client=payload.client,
        check_in=payload.check_in,
        check_out=payload.check_out,
        duration_min=payload.duration_min,
        km=payload.km,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    return ActivitateVisitCreated(
        id=visit.id,
        visit_date=visit.visit_date,
        agent_id=visit.agent_id,
        store_id=visit.store_id,
    )
