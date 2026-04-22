from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.mkt_sika import service as svc
from app.modules.mkt_sika.schemas import MktSikaResponse

router = APIRouter(prefix="/api/marketing/sika", tags=["marketing-sika"])


@router.get("", response_model=MktSikaResponse)
async def list_sika(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> MktSikaResponse:
    data = await svc.list_items(session, tenant_id)
    return MktSikaResponse.model_validate(data)
