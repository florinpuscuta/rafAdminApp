from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.discount_rules import service as svc
from app.modules.discount_rules.schemas import (
    DRBulkUpsertRequest,
    DRBulkUpsertResponse,
    DRClient,
    DRGroup,
    DRMatrixCell,
    DRMatrixResponse,
)
from app.modules.users.models import User


router = APIRouter(prefix="/api/discount-rules", tags=["discount-rules"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in svc.SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie 'adp' sau 'sika'"},
        )
    return s


@router.get("/matrix", response_model=DRMatrixResponse)
async def get_matrix(
    scope: str = Query("adp"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> DRMatrixResponse:
    s = _validate_scope(scope)
    data = await svc.get_matrix(session, tenant_id, s)
    return DRMatrixResponse(
        scope=data["scope"],
        clients=[DRClient(**c) for c in data["clients"]],
        groups=[DRGroup(**g) for g in data["groups"]],
        cells=[DRMatrixCell(**c) for c in data["cells"]],
    )


@router.post("/bulk-upsert", response_model=DRBulkUpsertResponse)
async def bulk_upsert(
    payload: DRBulkUpsertRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DRBulkUpsertResponse:
    s = _validate_scope(payload.scope)
    rules = [
        {
            "client_canonical": r.client_canonical,
            "group_kind": r.group_kind,
            "group_key": r.group_key,
            "applies": r.applies,
        }
        for r in payload.rules
    ]
    upserted, deleted = await svc.bulk_upsert(
        session,
        tenant_id=current_user.tenant_id,
        scope=s,
        rules=rules,
    )
    await audit_service.log_event(
        session,
        event_type="discount_rules.bulk_upsert",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="discount_rules",
        target_id=current_user.tenant_id,
        metadata={"scope": s, "upserted": upserted, "deleted": deleted},
    )
    return DRBulkUpsertResponse(upserted=upserted, deleted=deleted)
