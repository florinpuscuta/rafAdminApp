from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.top_produse import service as svc
from app.modules.top_produse.schemas import (
    TopProduseCategoryInfo,
    TopProduseMonthCell,
    TopProduseProductRow,
    TopProduseResponse,
    TopProduseTotals,
)

router = APIRouter(prefix="/api/top-produse", tags=["top-produse"])

_SCOPES = {"adp", "sika", "sikadp"}


def _pct(y1: Decimal, diff: Decimal) -> Decimal | None:
    return (diff / y1 * Decimal(100)) if y1 != 0 else None


def _product_to_model(p: svc.TopProductRow, rank: int) -> TopProduseProductRow:
    months: list[TopProduseMonthCell] = []
    for m in range(1, 13):
        cell = p.monthly.get(m)
        y1 = cell.sales_y1 if cell else Decimal(0)
        y2 = cell.sales_y2 if cell else Decimal(0)
        months.append(
            TopProduseMonthCell(
                month=m, month_name=svc.month_name(m),
                sales_y1=y1, sales_y2=y2,
            )
        )
    return TopProduseProductRow(
        rank=rank,
        product_id=p.product_id,
        product_code=p.product_code,
        product_name=p.product_name,
        sales_y1=p.sales_y1,
        sales_y2=p.sales_y2,
        qty_y1=p.qty_y1,
        qty_y2=p.qty_y2,
        diff=p.diff,
        pct=p.pct,
        price_y1=p.price_y1,
        price_y2=p.price_y2,
        monthly=months,
    )


def _build_response(
    scope: str,
    group_code: str,
    group_label: str,
    limit: int,
    data: dict,
    categories: list[dict],
) -> TopProduseResponse:
    products = [_product_to_model(p, i + 1) for i, p in enumerate(data["products"])]

    total_y1 = sum((p.sales_y1 for p in products), Decimal(0))
    total_y2 = sum((p.sales_y2 for p in products), Decimal(0))
    total_qty_y1 = sum((p.qty_y1 for p in products), Decimal(0))
    total_qty_y2 = sum((p.qty_y2 for p in products), Decimal(0))
    total_diff = total_y2 - total_y1

    return TopProduseResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        group=group_code,
        group_label=group_label,
        limit=limit,
        last_update=data["last_update"],
        products=products,
        totals=TopProduseTotals(
            sales_y1=total_y1, sales_y2=total_y2,
            qty_y1=total_qty_y1, qty_y2=total_qty_y2,
            diff=total_diff, pct=_pct(total_y1, total_diff),
        ),
        available_categories=[
            TopProduseCategoryInfo(id=c["id"], code=c["code"], label=c["label"])
            for c in categories
        ],
        ytd_months=data.get("ytd_months", []),
    )


@router.get("", response_model=TopProduseResponse)
async def get_top_produse(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    group: str = Query(..., min_length=1, max_length=50,
                       description="Codul categoriei, ex 'EPS', 'MU'"),
    year: int | None = Query(None, ge=2000, le=2100),
    limit: int = Query(20, ge=1, le=100),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope",
                    "message": "scope trebuie adp|sika|sikadp"},
        )

    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    # Scope=sika + cod TM → rută specială (Top 15 per Target Market).
    if scope == "sika" and svc.is_tm_code(group):
        tm_resolved = svc.resolve_tm(group)
        assert tm_resolved is not None
        tm_code, tm_label = tm_resolved
        parts_tm = []
        for tid in org_ids:
            parts_tm.append(await svc.get_for_sika_tm(
                session, tid,
                year_curr=year_curr, tm_label=tm_label, limit=limit,
            ))
        data = _merge_parts(parts_tm, limit) if len(parts_tm) > 1 else parts_tm[0]
        categories = await svc.list_categories(session)
        return _build_response(scope, tm_code, tm_label, limit, data, categories)

    resolved = await svc.resolve_category(session, group)
    if resolved is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_group",
                    "message": f"Categoria '{group}' nu există"},
        )
    category_id, group_label = resolved

    parts: list[dict] = []
    for tid in org_ids:
        if scope == "adp":
            d = await svc.get_for_adp(
                session, tid,
                year_curr=year_curr, category_id=category_id, limit=limit,
            )
        elif scope == "sika":
            d = await svc.get_for_sika(
                session, tid,
                year_curr=year_curr, category_id=category_id, limit=limit,
            )
        else:
            d = await svc.get_for_sikadp(
                session, tid,
                year_curr=year_curr, category_id=category_id, limit=limit,
            )
        parts.append(d)
    data = _merge_parts(parts, limit) if len(parts) > 1 else parts[0]

    categories = await svc.list_categories(session)
    return _build_response(scope, group.upper(), group_label, limit, data, categories)


def _merge_parts(parts: list[dict], limit: int) -> dict:
    """Produsele sunt unique per org (split pe brand). Concatenam si re-sortam."""
    all_products: list[svc.TopProductRow] = []
    last_update = None
    for p in parts:
        all_products.extend(p.get("products", []))
        if p.get("last_update") is not None:
            if last_update is None or p["last_update"] > last_update:
                last_update = p["last_update"]
    all_products.sort(key=lambda x: x.sales_y2, reverse=True)
    return {
        "products": all_products[:limit],
        "year_curr": parts[0]["year_curr"],
        "year_prev": parts[0]["year_prev"],
        "last_update": last_update,
        "ytd_months": parts[0].get("ytd_months", []),
    }
