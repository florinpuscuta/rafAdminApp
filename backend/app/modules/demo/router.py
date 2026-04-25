from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.core.schemas import APISchema
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_admin
from app.modules.demo import service as demo_service
from app.modules.users.models import User

router = APIRouter(prefix="/api/demo", tags=["demo"])


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


@router.post("/wipe", response_model=WipeResponse)
async def wipe_demo(
    request: Request,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Sterge toate datele tenantului (vanzari + entitati canonice + alias-uri +
    assignments + import batches). NU atinge users, organizatia, audit log,
    api keys.
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
