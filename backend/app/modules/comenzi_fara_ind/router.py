from datetime import date
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.comenzi_fara_ind import service as svc
from app.modules.comenzi_fara_ind.schemas import ComenziFaraIndResponse

router = APIRouter(prefix="/api/comenzi-fara-ind", tags=["comenzi-fara-ind"])

_SCOPES = {"adp", "sika"}


@router.get("", response_model=ComenziFaraIndResponse)
async def get_comenzi_fara_ind(
    scope: str = Query("adp", description="'adp' | 'sika' (SIKA returnează listă goală)"),
    report_date: date | None = Query(
        None,
        description="Default = cel mai recent snapshot (raw_orders.report_date) pentru source='adp'",
    ),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ComenziFaraIndResponse:
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika"},
        )

    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, report_date=report_date)
    else:
        data = await svc.get_for_sika(session, tenant_id, report_date=report_date)

    return ComenziFaraIndResponse.model_validate(data)
