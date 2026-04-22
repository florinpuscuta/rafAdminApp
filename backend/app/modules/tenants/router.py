from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_admin, get_current_user
from app.modules.tenants import service as tenants_service
from app.modules.tenants.schemas import TenantOut, UpdateTenantRequest
from app.modules.users.models import User

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("/current", response_model=TenantOut)
async def get_current_tenant(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tenant = await tenants_service.get_by_id(session, user.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TenantOut.model_validate(tenant)


@router.patch("/current", response_model=TenantOut)
async def update_current_tenant(
    request: Request,
    payload: UpdateTenantRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    tenant = await tenants_service.get_by_id(session, admin.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    changes: dict = {}
    if payload.name is not None and payload.name != tenant.name:
        changes["name"] = {"from": tenant.name, "to": payload.name}

    updated = await tenants_service.update_tenant(session, tenant, name=payload.name)
    if changes:
        await audit_service.log_event(
            session,
            event_type="tenant.updated",
            tenant_id=admin.tenant_id,
            user_id=admin.id,
            target_type="tenant",
            target_id=tenant.id,
            metadata=changes,
            request=request,
        )
    return TenantOut.model_validate(updated)


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_current_tenant(
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    tenant = await tenants_service.get_by_id(session, admin.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    await tenants_service.soft_delete(session, tenant)
    await audit_service.log_event(
        session,
        event_type="tenant.deactivated",
        tenant_id=tenant.id,
        user_id=admin.id,
        target_type="tenant",
        target_id=tenant.id,
        request=request,
    )
    return None
