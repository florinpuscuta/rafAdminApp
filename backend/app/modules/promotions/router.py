from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import (
    get_current_org_ids,
    get_current_tenant_id,
    get_current_user,
)
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
from app.modules.tenants.models import Organization
from app.modules.users.models import User
from sqlalchemy import select


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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> PromotionListResponse:
    promos: list[Promotion] = []
    for tid in org_ids:
        promos.extend(await svc.list_promotions(
            session, tid,
            scope=scope.lower() if scope else None,
            status=status_filter,
        ))
    items = [await _to_out(session, p) for p in promos]
    return PromotionListResponse(items=items)


@router.get("/products", response_model=ProductSearchResponse)
async def search_products(
    scope: str = Query("adp"),
    q: str = Query("", description="Filtru fuzzy pe cod sau nume"),
    limit: int = Query(500, ge=1, le=2000),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> ProductSearchResponse:
    s = _validate_scope(scope)
    seen: set[str] = set()
    merged: list[dict] = []
    for tid in org_ids:
        for it in await svc.search_products(
            session, tenant_id=tid, scope=s, q=q, limit=limit,
        ):
            if it["code"] in seen:
                continue
            seen.add(it["code"])
            merged.append(it)
    return ProductSearchResponse(items=[ProductSearchItem(**it) for it in merged])


@router.get("/groups", response_model=GroupsResponse)
async def list_groups(
    scope: str = Query("adp"),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> GroupsResponse:
    s = _validate_scope(scope)
    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []
    for tid in org_ids:
        for it in await svc.list_groups(session, tenant_id=tid, scope=s):
            sig = (it["kind"], it["key"])
            if sig in seen:
                continue
            seen.add(sig)
            merged.append(it)
    return GroupsResponse(items=[GroupOption(**it) for it in merged])


# IMPORTANT: rute cu segment literal ('/products', '/groups') TREBUIE
# declarate ÎNAINTE de '/{promo_id}' — altfel FastAPI încearcă să parseze
# 'products'/'groups' ca UUID și aruncă 422.
@router.get("/{promo_id}", response_model=PromotionOut)
async def get_promotion(
    promo_id: UUID,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    promo: Promotion | None = None
    for tid in org_ids:
        promo = await svc.get_promotion(session, tid, promo_id)
        if promo is not None:
            break
    if promo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    return await _to_out(session, promo)


_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession, user: User, org_ids: list[UUID], scope: str,
) -> UUID:
    """Map scope la org-ul corespunzător din membership-urile user-ului.

    În SIKADP consolidated mode org_ids are 2 entries — pickăm pe cel cu
    slug-ul matching ('adeplast' / 'sika'). În single-org mode, org_ids
    are 1 entry → folosim ăla.
    """
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
    return user.tenant_id


@router.post("", response_model=PromotionOut, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    payload: PromotionIn,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    _validate_payload(payload)
    target_tenant = await _resolve_tenant_for_scope(
        session, current_user, org_ids, payload.scope,
    )
    promo = await svc.create_promotion(
        session,
        tenant_id=target_tenant,
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
        tenant_id=target_tenant,
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    _validate_payload(payload)
    existing = None
    for tid in org_ids:
        existing = await svc.get_promotion(session, tid, promo_id)
        if existing is not None:
            break
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    promo = await svc.update_promotion(
        session,
        tenant_id=existing.tenant_id,
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
        tenant_id=existing.tenant_id,
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> None:
    existing = None
    for tid in org_ids:
        existing = await svc.get_promotion(session, tid, promo_id)
        if existing is not None:
            break
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "not_found", "message": "Promotie inexistenta",
        })
    await svc.delete_promotion(session, existing.tenant_id, promo_id)
    await audit_service.log_event(
        session,
        event_type="promotions.deleted",
        tenant_id=existing.tenant_id,
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
) -> PromoSimResponse:
    if baseline not in svc.BASELINE_KINDS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_baseline", "message": "baseline trebuie 'yoy' sau 'mom'"},
        )
    data = None
    for tid in org_ids:
        data = await svc.simulate(
            session, tenant_id=tid, promo_id=promo_id, baseline_kind=baseline,
        )
        if data is not None:
            break
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
