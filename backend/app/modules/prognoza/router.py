from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.prognoza import service as svc
from app.modules.prognoza.schemas import (
    PrognozaAgentRow,
    PrognozaForecastPoint,
    PrognozaHistoryPoint,
    PrognozaResponse,
)

router = APIRouter(prefix="/api/prognoza", tags=["prognoza"])

_SCOPES = {"adp", "sika", "sikadp"}


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
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )

    data = await svc.get_forecast(
        session, tenant_id, scope=scope, horizon_months=horizon_months,
    )
    return _build_response(data)
