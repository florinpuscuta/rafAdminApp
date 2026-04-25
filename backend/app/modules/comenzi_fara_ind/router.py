from datetime import date
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.comenzi_fara_ind import service as svc
from app.modules.comenzi_fara_ind.schemas import ComenziFaraIndResponse
from app.modules.tenants.models import Organization

router = APIRouter(prefix="/api/comenzi-fara-ind", tags=["comenzi-fara-ind"])

_SCOPES = {"adp", "sika"}
_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession, org_ids: list[UUID], scope: str,
) -> UUID:
    """În SIKADP user-ul are 2 org_ids; alegem pe cel cu slug-ul matching."""
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


@router.get("", response_model=ComenziFaraIndResponse)
async def get_comenzi_fara_ind(
    scope: str = Query("adp", description="'adp' | 'sika' (SIKA returnează listă goală)"),
    report_date: date | None = Query(
        None,
        description="Default = cel mai recent snapshot (raw_orders.report_date) pentru source='adp'",
    ),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> ComenziFaraIndResponse:
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika"},
        )

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)
    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, report_date=report_date)
    else:
        data = await svc.get_for_sika(session, tenant_id, report_date=report_date)

    return ComenziFaraIndResponse.model_validate(data)
