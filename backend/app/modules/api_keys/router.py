from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.api_keys import service as api_keys_service
from app.modules.api_keys.schemas import (
    ApiKeyOut,
    CreateApiKeyRequest,
    CreateApiKeyResponse,
)
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_admin
from app.modules.users.models import User

router = APIRouter(prefix="/api/api-keys", tags=["api_keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    keys = await api_keys_service.list_by_tenant(session, admin.tenant_id)
    return [ApiKeyOut.model_validate(k) for k in keys]


@router.post("", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    request: Request,
    payload: CreateApiKeyRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    key, raw = await api_keys_service.create(
        session,
        tenant_id=admin.tenant_id,
        created_by_user_id=admin.id,
        name=payload.name,
    )
    await audit_service.log_event(
        session,
        event_type="api_key.created",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="api_key",
        target_id=key.id,
        metadata={"name": payload.name, "prefix": key.prefix},
        request=request,
    )
    return CreateApiKeyResponse(api_key=ApiKeyOut.model_validate(key), secret=raw)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    request: Request,
    key_id: UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    key = await api_keys_service.get_by_id(session, admin.tenant_id, key_id)
    if key is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "api_key_not_found", "message": "API key inexistent"},
        )
    await api_keys_service.revoke(session, key)
    await audit_service.log_event(
        session,
        event_type="api_key.revoked",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        target_type="api_key",
        target_id=key.id,
        metadata={"name": key.name, "prefix": key.prefix},
        request=request,
    )
    return None
