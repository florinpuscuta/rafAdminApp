from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.promotions import service as svc
from app.modules.promotions.models import Promotion, PromotionTarget
from app.modules.promotions.schemas import (
    GroupOption,
    GroupsResponse,
    ProductSearchItem,
    ProductSearchResponse,
    PromoSimGroupRow,
    PromoSimResponse,
    PromotionIn,
    PromotionListResponse,
    PromotionOut,
    PromotionTargetOut,
)
from app.modules.users.models import User


router = APIRouter(prefix="/api/promotions", tags=["promotions"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in svc.SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie 'adp' sau 'sika'"},
        )
    return s


def _validate_payload(p: PromotionIn) -> None:
    if p.scope not in svc.SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope invalid"},
        )
    if p.discount_type not in svc.DISCOUNT_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_discount_type",
                "message": f"discount_type trebuie unul din {svc.DISCOUNT_TYPES}",
            },
        )
    if p.status not in svc.STATUSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_status", "message": f"status trebuie unul din {svc.STATUSES}"},
        )
    if p.valid_from > p.valid_to:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_period", "message": "valid_from > valid_to"},
        )
    for t in p.targets:
        if t.kind not in svc.TARGET_KINDS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_target_kind",
                    "message": f"target.kind trebuie unul din {svc.TARGET_KINDS}",
                },
            )


async def _to_out(
    session: AsyncSession, promo: Promotion,
) -> PromotionOut:
    targets = await svc.list_targets(session, promo.id)
    return PromotionOut(
        id=promo.id,
        scope=promo.scope, name=promo.name, status=promo.status,
        discount_type=promo.discount_type, value=promo.value,
        valid_from=promo.valid_from, valid_to=promo.valid_to,
        client_filter=promo.client_filter,
        notes=promo.notes,
        targets=[
            PromotionTargetOut(id=t.id, kind=t.kind, key=t.key)
            for t in targets
        ],
        created_at=promo.created_at, updated_at=promo.updated_at,
    )


@router.get("", response_model=PromotionListResponse)
async def list_promotions(
    scope: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PromotionListResponse:
    promos = await svc.list_promotions(
        session, tenant_id,
        scope=scope.lower() if scope else None,
        status=status_filter,
    )
    items = [await _to_out(session, p) for p in promos]
    return PromotionListResponse(items=items)


@router.get("/{promo_id}", response_model=PromotionOut)
async def get_promotion(
    promo_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    promo = await svc.get_promotion(session, tenant_id, promo_id)
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    return await _to_out(session, promo)


@router.post("", response_model=PromotionOut, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    payload: PromotionIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    _validate_payload(payload)
    promo = await svc.create_promotion(
        session,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        scope=payload.scope, name=payload.name, status=payload.status,
        discount_type=payload.discount_type, value=payload.value,
        valid_from=payload.valid_from, valid_to=payload.valid_to,
        client_filter=payload.client_filter,
        notes=payload.notes,
        targets=[t.model_dump() for t in payload.targets],
    )
    await audit_service.log_event(
        session,
        event_type="promotions.created",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="promotion",
        target_id=promo.id,
        metadata={"name": promo.name, "scope": promo.scope},
    )
    return await _to_out(session, promo)


@router.put("/{promo_id}", response_model=PromotionOut)
async def update_promotion(
    promo_id: UUID,
    payload: PromotionIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    _validate_payload(payload)
    promo = await svc.update_promotion(
        session,
        tenant_id=current_user.tenant_id,
        promo_id=promo_id,
        fields={
            "scope": payload.scope, "name": payload.name, "status": payload.status,
            "discount_type": payload.discount_type, "value": payload.value,
            "valid_from": payload.valid_from, "valid_to": payload.valid_to,
            "client_filter": payload.client_filter or None,
            "notes": payload.notes,
        },
        targets=[t.model_dump() for t in payload.targets],
    )
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    await audit_service.log_event(
        session,
        event_type="promotions.updated",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="promotion",
        target_id=promo.id,
        metadata={"name": promo.name, "status": promo.status},
    )
    return await _to_out(session, promo)


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promotion(
    promo_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    ok = await svc.delete_promotion(session, current_user.tenant_id, promo_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    await audit_service.log_event(
        session,
        event_type="promotions.deleted",
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        target_type="promotion",
        target_id=promo_id,
        metadata={},
    )
    return None


@router.post("/{promo_id}/simulate", response_model=PromoSimResponse)
async def simulate(
    promo_id: UUID,
    baseline: str = Query("yoy", description="'yoy' | 'mom'"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PromoSimResponse:
    if baseline not in svc.BASELINE_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_baseline", "message": "baseline trebuie 'yoy' sau 'mom'"},
        )
    data = await svc.simulate(
        session, tenant_id=tenant_id, promo_id=promo_id, baseline_kind=baseline,
    )
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    return PromoSimResponse(
        promotion_id=data["promotion_id"],
        baseline_kind=data["baseline_kind"],
        baseline_label=data["baseline_label"],
        promo_label=data["promo_label"],
        products_in_scope=data["products_in_scope"],
        baseline_revenue=data["baseline_revenue"],
        baseline_cost=data["baseline_cost"],
        baseline_profit=data["baseline_profit"],
        baseline_margin_pct=data["baseline_margin_pct"],
        scenario_revenue=data["scenario_revenue"],
        scenario_cost=data["scenario_cost"],
        scenario_profit=data["scenario_profit"],
        scenario_margin_pct=data["scenario_margin_pct"],
        delta_revenue=data["delta_revenue"],
        delta_profit=data["delta_profit"],
        delta_margin_pp=data["delta_margin_pp"],
        groups=[PromoSimGroupRow(**g) for g in data["groups"]],
    )


@router.get("/products", response_model=ProductSearchResponse)
async def search_products(
    scope: str = Query("adp"),
    q: str = Query("", description="Filtru fuzzy pe cod sau nume"),
    limit: int = Query(500, ge=1, le=2000),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> ProductSearchResponse:
    s = _validate_scope(scope)
    items = await svc.search_products(
        session, tenant_id=tenant_id, scope=s, q=q, limit=limit,
    )
    return ProductSearchResponse(items=[ProductSearchItem(**it) for it in items])


@router.get("/groups", response_model=GroupsResponse)
async def list_groups(
    scope: str = Query("adp"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> GroupsResponse:
    s = _validate_scope(scope)
    items = await svc.list_groups(session, tenant_id=tenant_id, scope=s)
    return GroupsResponse(items=[GroupOption(**it) for it in items])
