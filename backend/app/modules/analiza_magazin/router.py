from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.analiza_magazin import service as svc
from app.modules.analiza_magazin.schemas import (
    AMCategoryBreakdown,
    AMGapProduct,
    AMResponse,
    AMStoreOption,
    AMStoresResponse,
)
from app.modules.auth.deps import get_current_tenant_id

router = APIRouter(prefix="/api/analiza-magazin", tags=["analiza-magazin"])

_SCOPES = {"adp", "sika"}


def _validate_scope(scope: str) -> str:
    s = scope.lower()
    if s not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp' sau 'sika'",
            },
        )
    return s


def _validate_months(months: int) -> int:
    if months not in svc.ALLOWED_MONTHS_WINDOWS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_months",
                "message": f"months trebuie sa fie unul din {svc.ALLOWED_MONTHS_WINDOWS}",
            },
        )
    return months


@router.get("/stores", response_model=AMStoresResponse)
async def list_stores(
    scope: str = Query("adp", description="'adp' | 'sika'"),
    months: int = Query(svc.MONTHS_WINDOW, description="3 | 6 | 9 | 12"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    s = _validate_scope(scope)
    m = _validate_months(months)
    stores = await svc.list_stores(session, tenant_id, scope=s, months_window=m)
    return AMStoresResponse(
        scope=s,
        months_window=m,
        stores=[
            AMStoreOption(key=x.key, label=x.key, chain=x.chain, agent=x.agent)
            for x in stores
        ],
    )


@router.get("", response_model=AMResponse)
async def get_analiza_magazin(
    scope: str = Query("adp", description="'adp' | 'sika'"),
    store: str = Query(..., min_length=1,
                       description="Numele magazinului (RawSale.client)"),
    months: int = Query(svc.MONTHS_WINDOW, description="3 | 6 | 9 | 12"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    s = _validate_scope(scope)
    m = _validate_months(months)
    result = await svc.get_gap(
        session, tenant_id, scope=s, store=store, months_window=m,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "store_not_found",
                "message": (
                    "Magazinul nu aparține unui chain cunoscut sau nu are "
                    f"date în ultimele {m} luni."
                ),
            },
        )
    return AMResponse(
        scope=result.scope,
        store=result.store,
        chain=result.chain,
        months_window=result.months_window,
        chain_sku_count=result.chain_sku_count,
        own_sku_count=result.own_sku_count,
        gap_count=len(result.gap),
        gap=[
            AMGapProduct(
                product_id=p.product_id,
                product_code=p.product_code,
                product_name=p.product_name,
                category=p.category,
                chain_qty=p.chain_qty,
                chain_value=p.chain_value,
                stores_selling_count=p.stores_selling_count,
            )
            for p in result.gap
        ],
        breakdown=[
            AMCategoryBreakdown(
                category=b.category,
                chain_sku_count=b.chain_sku_count,
                own_sku_count=b.own_sku_count,
                gap_count=b.gap_count,
            )
            for b in result.breakdown
        ],
    )
