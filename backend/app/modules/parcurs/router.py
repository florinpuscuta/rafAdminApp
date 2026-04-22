"""
Router pentru /api/parcurs — Foaia de Parcurs.

Rute:
  GET  /api/parcurs/agents
  GET  /api/parcurs/stores?agent=...
  POST /api/parcurs/generate   — generează + persistă (upsert)
  GET  /api/parcurs/sheets     — listă foi istorice
"""
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.parcurs import service as svc
from app.modules.parcurs.schemas import (
    ParcursAgentOption,
    ParcursAgentsResponse,
    ParcursGenerateRequest,
    ParcursResponse,
    ParcursSheetsListResponse,
    ParcursSheetSummary,
    ParcursStoreOption,
    ParcursStoresResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/parcurs", tags=["parcurs"])

_SCOPES = {"adp", "sika", "sikadp"}


def _check_scope(scope: str) -> str:
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )
    return scope


@router.get("/agents", response_model=ParcursAgentsResponse)
async def get_agents(
    scope: str = Query("adp"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(scope)
    agents = await svc.list_agents(session, tenant_id, scope=scope)
    return ParcursAgentsResponse(
        scope=scope,
        agents=[ParcursAgentOption(**a) for a in agents],
    )


@router.get("/stores", response_model=ParcursStoresResponse)
async def get_stores(
    scope: str = Query("adp"),
    agent: str = Query(..., min_length=1),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(scope)
    stores = await svc.list_stores_for_agent(
        session, tenant_id, scope=scope, agent_name=agent,
    )
    return ParcursStoresResponse(
        scope=scope,
        agent=agent,
        stores=[ParcursStoreOption(**s) for s in stores],
    )


@router.post("/generate", response_model=ParcursResponse)
async def generate(
    payload: ParcursGenerateRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _check_scope(payload.scope)
    data = await svc.generate(
        session, tenant_id, req=payload, created_by_user_id=user.id,
    )
    return ParcursResponse(**data)


@router.get("/sheets", response_model=ParcursSheetsListResponse)
async def list_sheets(
    scope: str = Query("adp"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = _check_scope(scope)
    sheets = await svc.list_sheets(session, tenant_id, scope=scope)
    return ParcursSheetsListResponse(
        scope=scope,
        sheets=[ParcursSheetSummary(**s) for s in sheets],
    )
