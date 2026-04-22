from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.brands import service as brands_service
from app.modules.brands.schemas import BrandCreate, BrandOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/brands", tags=["brands"])


@router.get("", response_model=list[BrandOut])
async def list_brands(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    brands = await brands_service.list_by_tenant(session, tenant_id)
    return [BrandOut.model_validate(b) for b in brands]


@router.post("", response_model=BrandOut, status_code=201)
async def create_brand(
    payload: BrandCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    brand = await brands_service.create(
        session,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        is_private_label=payload.is_private_label,
        sort_order=payload.sort_order,
    )
    await session.commit()
    return BrandOut.model_validate(brand)
