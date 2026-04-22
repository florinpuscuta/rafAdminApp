from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.core.schemas import APISchema
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_admin
from app.modules.demo import service as demo_service
from app.modules.users.models import User

router = APIRouter(prefix="/api/demo", tags=["demo"])


class SeedResponse(APISchema):
    stores: int
    agents: int
    products: int
    sales: int
    assignments: int


class WipeResponse(APISchema):
    sales: int
    batches: int
    assignments: int
    store_aliases: int
    agent_aliases: int
    product_aliases: int
    stores: int
    agents: int
    products: int


@router.post("/seed", response_model=SeedResponse)
async def seed_demo(
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Populează tenantul cu date sintetice. Refuză dacă există deja date."""
    try:
        counts = await demo_service.seed_demo_data(
            session, tenant_id=admin.tenant_id, user_id=admin.id,
        )
    except ValueError as exc:
        if str(exc) == "not_empty":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "code": "tenant_not_empty",
                    "message": "Tenantul are deja date. Folosește /api/demo/wipe întâi dacă vrei reset.",
                },
            )
        raise
    await audit_service.log_event(
        session,
        event_type="demo.seeded",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        metadata=counts,
        request=request,
    )
    return SeedResponse(**counts)


@router.post("/wipe", response_model=WipeResponse)
async def wipe_demo(
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Șterge toate datele tenantului (vânzări + entități canonice + alias-uri +
    assignments + import batches). NU atinge users, tenant, audit log, api keys.
    """
    counts = await demo_service.wipe_tenant_data(session, tenant_id=admin.tenant_id)
    await audit_service.log_event(
        session,
        event_type="demo.wiped",
        tenant_id=admin.tenant_id,
        user_id=admin.id,
        metadata=counts,
        request=request,
    )
    return WipeResponse(**counts)
