from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.prognoza import service as svc
from app.modules.prognoza.schemas import (
    PrognozaAgentRow,
    PrognozaForecastPoint,
    PrognozaHistoryPoint,
    PrognozaResponse,
)
from app.modules.tenants.models import Organization

router = APIRouter(prefix="/api/prognoza", tags=["prognoza"])

_SCOPES = {"adp", "sika", "sikadp"}
_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession, org_ids: list[UUID], scope: str,
) -> UUID:
    if len(org_ids) == 1:
        return org_ids[0]
    target_slug = _SCOPE_TO_SLUG.get(scope)
    if target_slug:
        res = await session.execute(
            select(Organization.id).where(
                Organization.id.in_(org_ids),
                Organization.slug == target_slug,
            )
        )
        match = res.scalar_one_or_none()
        if match is not None:
            return match
    return org_ids[0]


def _build_response(data: dict) -> PrognozaResponse:
    history = [PrognozaHistoryPoint(**p) for p in data["history"]]
    forecast = [PrognozaForecastPoint(**p) for p in data["forecast"]]
    agents = [PrognozaAgentRow(**a) for a in data["agents"]]
    return PrognozaResponse(
        scope=data["scope"],
        horizon_months=data["horizon_months"],
        method=data["method"],
        last_update=data["last_update"],
        last_complete_month=data["last_complete_month"],
        history=history,
        forecast=forecast,
        agents=agents,
    )


@router.get("", response_model=PrognozaResponse)
async def get_prognoza(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    horizon_months: int = Query(3, ge=1, le=12, description="Orizont 1..12 luni"),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)

    data = await svc.get_forecast(
        session, tenant_id, scope=scope, horizon_months=horizon_months,
    )
    return _build_response(data)
