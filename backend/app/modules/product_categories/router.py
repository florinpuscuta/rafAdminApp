from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_user
from app.modules.product_categories import service as service
from app.modules.product_categories.schemas import ProductCategoryOut
from app.modules.users.models import User

router = APIRouter(prefix="/api/product-categories", tags=["product-categories"])


@router.get("", response_model=list[ProductCategoryOut])
async def list_categories(
    _current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Listează categoriile globale (aceleași pentru toți tenanții). Require
    doar autentificare — nu scope tenant, e catalog SaaS-level.
    """
    cats = await service.list_all(session)
    return [ProductCategoryOut.model_validate(c) for c in cats]
