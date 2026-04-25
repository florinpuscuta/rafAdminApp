from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.grupe_produse import service as svc
from app.modules.grupe_produse.schemas import (
    GrupeProduseCategoryInfo,
    GrupeProduseProductRow,
    GrupeProduseResponse,
    GrupeProduseTotals,
    GrupeProduseTreeByClientResponse,
    GrupeProduseTreeResponse,
)
from app.modules.tenants.models import Organization

router = APIRouter(prefix="/api/grupe-produse", tags=["grupe-produse"])

_SCOPES = {"adp", "sika", "sikadp"}
_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession, org_ids: list[UUID], scope: str,
) -> UUID:
    """In SIKADP user-ul are 2 org_ids; alegem pe cel cu slug-ul matching.
    Pentru scope='sikadp' returnam primul (service-ul face merging singur)."""
    if len(org_ids) == 1:
        return org_ids[0]
    target_slug = _SCOPE_TO_SLUG.get(scope)
    if target_slug:
        res = await session.execute(
            select(Organization.id).where(
                Organization.id.in_(org_ids),
                Organization.slug == target_slug,
            )
        )
        match = res.scalar_one_or_none()
        if match is not None:
            return match
    return org_ids[0]


def _pct(y1: Decimal, diff: Decimal) -> Decimal | None:
    return (diff / y1 * Decimal(100)) if y1 != 0 else None


def _product_to_model(p: svc.ProductRow) -> GrupeProduseProductRow:
    return GrupeProduseProductRow(
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
    )


def _build_response(
    scope: str,
    group_code: str,
    group_label: str,
    data: dict,
    categories: list[dict],
) -> GrupeProduseResponse:
    products = [_product_to_model(p) for p in data["products"]]

    total_y1 = sum((p.sales_y1 for p in products), Decimal(0))
    total_y2 = sum((p.sales_y2 for p in products), Decimal(0))
    total_qty_y1 = sum((p.qty_y1 for p in products), Decimal(0))
    total_qty_y2 = sum((p.qty_y2 for p in products), Decimal(0))
    total_diff = total_y2 - total_y1

    return GrupeProduseResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        group=group_code,
        group_label=group_label,
        last_update=data["last_update"],
        products=products,
        totals=GrupeProduseTotals(
            sales_y1=total_y1, sales_y2=total_y2,
            qty_y1=total_qty_y1, qty_y2=total_qty_y2,
            diff=total_diff, pct=_pct(total_y1, total_diff),
        ),
        available_categories=[
            GrupeProduseCategoryInfo(id=c["id"], code=c["code"], label=c["label"])
            for c in categories
        ],
    )


@router.get("", response_model=GrupeProduseResponse)
async def get_grupe_produse(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    group: str = Query(..., min_length=1, max_length=50,
                       description="Codul categoriei, ex 'EPS', 'MU'"),
    year: int | None = Query(None, ge=2000, le=2100),
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

    resolved = await svc.resolve_category(session, group)
    if resolved is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "unknown_group",
                    "message": f"Categoria '{group}' nu există"},
        )
    category_id, group_label = resolved

    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)

    if scope == "adp":
        data = await svc.get_for_adp(
            session, tenant_id, year_curr=year_curr, category_id=category_id,
        )
    elif scope == "sika":
        data = await svc.get_for_sika(
            session, tenant_id, year_curr=year_curr, category_id=category_id,
        )
    else:
        data = await svc.get_for_sikadp(
            session, tenant_id, year_curr=year_curr, category_id=category_id,
        )

    categories = await svc.list_categories(session)
    return _build_response(scope, group.upper(), group_label, data, categories)


@router.get("/tree", response_model=GrupeProduseTreeResponse)
async def get_tree(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, ge=2000, le=2100),
    months: str | None = Query(
        None,
        description=(
            "Luni ca CSV (ex. '1,2,3'). "
            "Omis = YTD auto (default). "
            "String gol = niciuna (rezultat gol). "
            "'all' = tot anul."
        ),
    ),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """Arbore Brand → Categorie → Produs, sortat DESC pe toate nivelurile.
    Marca Privată e mereu listată separat la sfârșit (flag is_private_label)."""
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope",
                    "message": "scope trebuie adp|sika|sikadp"},
        )
    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    # Parse months: None → YTD auto; "all" → 1..12; "" → []; CSV → list[int].
    months_list: list[int] | None
    if months is None:
        months_list = None
    elif months.strip().lower() == "all":
        months_list = list(range(1, 13))
    elif months.strip() == "":
        months_list = []
    else:
        try:
            months_list = [
                int(x.strip()) for x in months.split(",") if x.strip()
            ]
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_months",
                        "message": "months trebuie CSV de numere 1..12"},
            )

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)
    data = await svc.build_tree(
        session, tenant_id, scope=scope, year=year_curr, months=months_list,
    )
    return GrupeProduseTreeResponse(**data)


@router.get("/tree-by-client", response_model=GrupeProduseTreeByClientResponse)
async def get_tree_by_client(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, ge=2000, le=2100),
    months: str | None = Query(
        None,
        description=(
            "Luni ca CSV (ex. '1,2,3'). "
            "Omis = YTD auto (default). "
            "String gol = niciuna. "
            "'all' = tot anul."
        ),
    ),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """Arbore Client (rețea) → Categorie → Produs — aceeași structură ca
    `/tree` dar agrupat pe rețeaua parteneră (Dedeman/Altex/Leroy/Hornbach/Alte)."""
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope",
                    "message": "scope trebuie adp|sika|sikadp"},
        )
    now = datetime.now(timezone.utc)
    year_curr = year or now.year

    months_list: list[int] | None
    if months is None:
        months_list = None
    elif months.strip().lower() == "all":
        months_list = list(range(1, 13))
    elif months.strip() == "":
        months_list = []
    else:
        try:
            months_list = [
                int(x.strip()) for x in months.split(",") if x.strip()
            ]
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_months",
                        "message": "months trebuie CSV de numere 1..12"},
            )

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)
    data = await svc.build_tree_by_client(
        session, tenant_id, scope=scope, year=year_curr, months=months_list,
    )
    return GrupeProduseTreeByClientResponse(**data)
