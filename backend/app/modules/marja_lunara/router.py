from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.margine import service as margine_svc
from app.modules.marja_lunara import service as svc
from app.modules.marja_lunara.schemas import (
    MarjaLunaraResponse,
    MLGroupRow,
    MLMonthRow,
)


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    return num / den if den != 0 else Decimal(0)


def _consolidate_months(
    parts: list[svc.MarjaLunaraData],
) -> svc.MarjaLunaraData:
    """Suma cifrelor pe luni din N raspunsuri per-org."""
    first = parts[0]
    months_by_key: dict[tuple[int, int], svc.MLMonth] = {}
    for p in parts:
        for m in p.months:
            key = (m.year, m.month)
            existing = months_by_key.get(key)
            if existing is None:
                months_by_key[key] = svc.MLMonth(
                    year=m.year, month=m.month,
                    revenue_period=m.revenue_period,
                    revenue_covered=m.revenue_covered,
                    cost_total=m.cost_total,
                    profit_total=m.profit_total,
                    margin_pct=m.margin_pct,
                    discount_total=m.discount_total,
                    discount_allocated_total=m.discount_allocated_total,
                    profit_net_total=m.profit_net_total,
                    margin_pct_net=m.margin_pct_net,
                    has_monthly_snapshot=m.has_monthly_snapshot,
                    fallback_revenue_pct=m.fallback_revenue_pct,
                    products_with_cost=m.products_with_cost,
                    products_missing_cost=m.products_missing_cost,
                    groups=list(m.groups),
                )
                continue
            existing.revenue_period += m.revenue_period
            existing.revenue_covered += m.revenue_covered
            existing.cost_total += m.cost_total
            existing.profit_total = existing.revenue_covered - existing.cost_total
            existing.margin_pct = _safe_div(existing.profit_total, existing.revenue_covered) * Decimal(100)
            existing.discount_total += m.discount_total
            existing.discount_allocated_total += m.discount_allocated_total
            existing.profit_net_total = existing.profit_total + existing.discount_allocated_total
            existing.margin_pct_net = _safe_div(existing.profit_net_total, existing.revenue_covered) * Decimal(100)
            existing.has_monthly_snapshot = existing.has_monthly_snapshot or m.has_monthly_snapshot
            # fallback_revenue_pct: media ponderata pe revenue_covered
            existing.products_with_cost += m.products_with_cost
            existing.products_missing_cost += m.products_missing_cost

            # Merge groups (kind, key)
            gmap = {(g.kind, g.key): g for g in existing.groups}
            for g in m.groups:
                k = (g.kind, g.key)
                eg = gmap.get(k)
                if eg is None:
                    existing.groups.append(g)
                    gmap[k] = g
                    continue
                eg.revenue += g.revenue
                eg.quantity += g.quantity
                eg.cost_total += g.cost_total
                eg.profit += g.profit
                eg.discount_allocated += g.discount_allocated
                eg.profit_net = eg.profit + eg.discount_allocated
                eg.margin_pct = _safe_div(eg.profit, eg.revenue) * Decimal(100)
                eg.margin_pct_net = _safe_div(eg.profit_net, eg.revenue) * Decimal(100)

    months = sorted(months_by_key.values(), key=lambda x: (x.year, x.month))
    return svc.MarjaLunaraData(
        scope=first.scope,
        from_year=first.from_year, from_month=first.from_month,
        to_year=first.to_year, to_month=first.to_month,
        months=months,
    )


router = APIRouter(prefix="/api/marja-lunara", tags=["marja-lunara"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in margine_svc.SCOPE_SOURCES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp', 'sika' sau 'sikadp'",
            },
        )
    return s


def _validate_period(fy: int, fm: int, ty: int, tm: int) -> None:
    if not (1 <= fm <= 12) or not (1 <= tm <= 12):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "month trebuie 1..12"},
        )
    if (fy, fm) > (ty, tm):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_period", "message": "from > to"},
        )


@router.get("", response_model=MarjaLunaraResponse)
async def get_marja_lunara(
    scope: str = Query("adp"),
    from_year: int = Query(..., alias="fromYear"),
    from_month: int = Query(..., alias="fromMonth"),
    to_year: int = Query(..., alias="toYear"),
    to_month: int = Query(..., alias="toMonth"),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> MarjaLunaraResponse:
    s = _validate_scope(scope)
    _validate_period(from_year, from_month, to_year, to_month)
    parts: list[svc.MarjaLunaraData] = []
    for tid in org_ids:
        parts.append(await svc.build_marja_lunara(
            session,
            tenant_id=tid, scope=s,
            from_year=from_year, from_month=from_month,
            to_year=to_year, to_month=to_month,
        ))
    data = parts[0] if len(parts) == 1 else _consolidate_months(parts)
    return MarjaLunaraResponse(
        scope=data.scope,
        from_year=data.from_year, from_month=data.from_month,
        to_year=data.to_year, to_month=data.to_month,
        months=[
            MLMonthRow(
                year=m.year, month=m.month,
                revenue_period=m.revenue_period,
                revenue_covered=m.revenue_covered,
                cost_total=m.cost_total,
                profit_total=m.profit_total,
                margin_pct=m.margin_pct,
                discount_total=m.discount_total,
                discount_allocated_total=m.discount_allocated_total,
                profit_net_total=m.profit_net_total,
                margin_pct_net=m.margin_pct_net,
                has_monthly_snapshot=m.has_monthly_snapshot,
                fallback_revenue_pct=m.fallback_revenue_pct,
                products_with_cost=m.products_with_cost,
                products_missing_cost=m.products_missing_cost,
                groups=[
                    MLGroupRow(
                        label=g.label, kind=g.kind, key=g.key,
                        revenue=g.revenue, quantity=g.quantity,
                        cost_total=g.cost_total, profit=g.profit,
                        margin_pct=g.margin_pct,
                        discount_allocated=g.discount_allocated,
                        profit_net=g.profit_net,
                        margin_pct_net=g.margin_pct_net,
                    )
                    for g in m.groups
                ],
            )
            for m in data.months
        ],
    )
