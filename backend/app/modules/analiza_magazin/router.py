from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.analiza_magazin import service as svc
from app.modules.analiza_magazin.schemas import (
    AMCategoryBreakdown,
    AMGapProduct,
    AMInsightsResponse,
    AMMustListProduct,
    AMRank,
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


@router.get("/insights", response_model=AMInsightsResponse)
async def get_insights(
    scope: str = Query("adp", description="'adp' | 'sika'"),
    store: str = Query(..., min_length=1,
                       description="Numele magazinului (RawSale.client)"),
    months: int = Query(svc.MONTHS_WINDOW, description="3 | 6 | 9 | 12"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Insights pentru un magazin:
      - rank în clasamentul scope-ului (după valoare totală + nr SKU-uri)
      - top 5 produse "obligatoriu de listat" cu estimare revenue 12 luni

    Estimarea folosește vânzarea medie / lună / magazin care listează produsul,
    proiectată pe 12 luni și ajustată cu un size_factor (vânzările magazinului
    țintă vs media scope-ului), clip la [0.3×, 3×].
    """
    s = _validate_scope(scope)
    m = _validate_months(months)
    result = await svc.compute_insights(
        session, tenant_id, scope=s, store=store, months_window=m,
    )
    if result is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "no_insights",
                "message": (
                    "Magazinul nu are date suficiente în ultimele "
                    f"{m} luni (sau nu aparține unui chain cunoscut)."
                ),
            },
        )
    return AMInsightsResponse(
        scope=result.scope,
        store=result.store,
        chain=result.chain,
        months_window=result.months_window,
        rank_by_value=AMRank(
            rank=result.rank_by_value.rank,
            total=result.rank_by_value.total,
            pct_top=result.rank_by_value.pct_top,
        ),
        rank_by_skus=AMRank(
            rank=result.rank_by_skus.rank,
            total=result.rank_by_skus.total,
            pct_top=result.rank_by_skus.pct_top,
        ),
        store_total_value=result.store_total_value,
        store_sku_count=result.store_sku_count,
        must_list=[
            AMMustListProduct(
                product_id=p.product_id,
                product_code=p.product_code,
                product_name=p.product_name,
                category=p.category,
                listed_in_stores=p.listed_in_stores,
                total_stores=p.total_stores,
                monthly_avg_per_listed=p.monthly_avg_per_listed,
                estimated_window_revenue=p.estimated_window_revenue,
                estimated_window_quantity=p.estimated_window_quantity,
                estimated_12m_revenue=p.estimated_12m_revenue,
                rationale=p.rationale,
            )
            for p in result.must_list
        ],
    )
