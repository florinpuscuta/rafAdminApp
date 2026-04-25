from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.analiza_magazin_dashboard import service as svc
from app.modules.analiza_magazin_dashboard.schemas import (
    AMDBrandSplit,
    AMDCategoryRow,
    AMDClientsResponse,
    AMDDashboardResponse,
    AMDMetrics,
    AMDMonthSeries,
    AMDPair,
    AMDStoreOption,
    AMDStoresResponse,
)
from app.modules.auth.deps import get_current_tenant_id

router = APIRouter(
    prefix="/api/analiza-magazin-dashboard",
    tags=["analiza-magazin-dashboard"],
)


def _validate_scope(scope: str) -> str:
    s = scope.lower()
    if s not in svc.SCOPE_SOURCES:
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
                "message": (
                    f"months trebuie sa fie unul din {svc.ALLOWED_MONTHS_WINDOWS}"
                ),
            },
        )
    return months


def _metrics(m: svc.Metrics) -> AMDMetrics:
    return AMDMetrics(
        sales=m.sales, quantity=m.quantity, sku_count=m.sku_count,
    )


@router.get("/clients", response_model=AMDClientsResponse)
async def list_clients() -> AMDClientsResponse:
    return AMDClientsResponse(clients=svc.list_clients())


@router.get("/stores", response_model=AMDStoresResponse)
async def list_stores(
    client: str = Query(..., min_length=1, description="Eticheta clientului KA"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> AMDStoresResponse:
    if client not in svc.KA_CLIENTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_client",
                "message": (
                    f"client trebuie sa fie unul din {list(svc.KA_CLIENTS.keys())}"
                ),
            },
        )
    stores = await svc.list_stores_for_client(
        session, tenant_id, client=client,
    )
    return AMDStoresResponse(
        client=client,
        stores=[
            AMDStoreOption(store_id=s.store_id, name=s.name) for s in stores
        ],
    )


@router.get("", response_model=AMDDashboardResponse)
async def get_dashboard(
    scope: str = Query("adp", description="'adp' | 'sika'"),
    store_id: UUID = Query(..., description="ID magazin canonic (Store.id)"),
    months: int = Query(svc.DEFAULT_MONTHS_WINDOW, description="3 | 6 | 9 | 12"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> AMDDashboardResponse:
    s = _validate_scope(scope)
    m = _validate_months(months)
    data = await svc.build_dashboard(
        session, tenant_id, scope=s, store_id=store_id, months_window=m,
    )
    if data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={
                "code": "store_not_found",
                "message": "Magazinul nu există în tenant.",
            },
        )
    return AMDDashboardResponse(
        scope=data.scope,
        store_id=data.store_id,
        store_name=data.store_name,
        months_window=data.months_window,
        window_curr=[AMDPair(year=y, month=mm) for (y, mm) in data.window_curr],
        window_yoy=[AMDPair(year=y, month=mm) for (y, mm) in data.window_yoy],
        window_prev=[AMDPair(year=y, month=mm) for (y, mm) in data.window_prev],
        kpi_curr=_metrics(data.kpi_curr),
        kpi_yoy=_metrics(data.kpi_yoy),
        kpi_prev=_metrics(data.kpi_prev),
        monthly=[
            AMDMonthSeries(
                year=ms.year, month=ms.month,
                sales_curr=ms.sales_curr, sales_prev_year=ms.sales_prev_year,
                sku_curr=ms.sku_curr, sku_prev_year=ms.sku_prev_year,
            )
            for ms in data.monthly
        ],
        categories=[
            AMDCategoryRow(
                code=c.code, label=c.label,
                curr=_metrics(c.curr), yoy=_metrics(c.yoy),
            )
            for c in data.categories
        ],
        brand_split=AMDBrandSplit(
            brand=_metrics(data.brand_split.brand),
            private_label=_metrics(data.brand_split.private_label),
            brand_yoy=_metrics(data.brand_split.brand_yoy),
            private_label_yoy=_metrics(data.brand_split.private_label_yoy),
        ),
    )
