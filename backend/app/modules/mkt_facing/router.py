"""
Facing Tracker router — port 1:1 al `adeplast-dashboard/routes/facing.py`.

Toate endpoint-urile legacy sunt aici (prefix `/api/marketing/facing`):
  GET    /config
  GET    /tree
  POST   /migrate-month
  GET    /chain-brands
  POST   /chain-brands
  POST   /raioane
  PUT    /raioane/{rid}
  DELETE /raioane/{rid}
  POST   /brands
  PUT    /brands/{bid}
  DELETE /brands/{bid}
  GET    /stores
  DELETE /store
  GET    /snapshots
  POST   /save
  GET    /evolution
  GET    /dashboard
  GET    /months
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import (
    get_current_org_ids,
    get_current_tenant_id,
    get_current_user,
)
from app.modules.mkt_facing import service as svc
from app.modules.mkt_facing.schemas import (
    BrandCreateBody,
    BrandUpdateBody,
    ChainBrandsResponse,
    ChainBrandsSaveBody,
    ConfigResponse,
    DashboardResponse,
    EvolutionResponse,
    MigrateMonthBody,
    MigrateMonthResponse,
    MonthsResponse,
    OkResponse,
    RaionCompetitorsMatrix,
    RaionCompetitorsSaveBody,
    RaionCreateBody,
    RaionShareResponse,
    RaionUpdateBody,
    SaveBody,
    SaveResponse,
    SnapshotsResponse,
    StoreDeleteResponse,
    StoresResponse,
    TreeResponse,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/marketing/facing", tags=["marketing-facing"])


# ── Config: raioane + brands ────────────────────────────────────────────────

@router.get("/config", response_model=ConfigResponse)
async def api_config(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    return ConfigResponse.model_validate({
        "raioane": await svc.get_raioane_by_tenants(session, org_ids),
        "raioane_tree": await svc.get_raioane_tree_by_tenants(session, org_ids),
        "brands": await svc.get_brands_by_tenants(session, org_ids),
        "chain_brands": await svc.get_chain_brands_by_tenants(session, org_ids),
        "chains": svc.DEFAULT_CHAINS,
    })


@router.get("/tree", response_model=TreeResponse)
async def api_tree(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    return TreeResponse(
        tree=await svc.get_raioane_tree_by_tenants(session, org_ids),
    )


@router.post("/migrate-month", response_model=MigrateMonthResponse)
async def api_migrate_month(
    body: MigrateMonthBody,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    luna = (body.luna or "").strip()
    if not luna:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail={"ok": False, "error": "Luna lipseste"},
        )
    migrated, details = await svc.migrate_month_to_children(
        session, tenant_id, luna, user=current_user.email or "",
    )
    return MigrateMonthResponse(migrated=migrated, details=details, luna=luna)


@router.get("/chain-brands", response_model=ChainBrandsResponse)
async def api_chain_brands_get(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    return ChainBrandsResponse(
        chain_brands=await svc.get_chain_brands_by_tenants(session, org_ids),
        chains=svc.DEFAULT_CHAINS,
    )


@router.post("/chain-brands", response_model=OkResponse)
async def api_chain_brands_save(
    body: ChainBrandsSaveBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    await svc.set_chain_brands_bulk(session, tenant_id, body.matrix)
    return OkResponse()


@router.post("/raioane", response_model=OkResponse)
async def api_raion_add(
    body: RaionCreateBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Numele este obligatoriu"},
        )
    await svc.add_raion(session, tenant_id, name, parent_id=body.parent_id)
    return OkResponse()


@router.put("/raioane/{rid}", response_model=OkResponse)
async def api_raion_update(
    rid: UUID,
    body: RaionUpdateBody,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Numele este obligatoriu"},
        )
    # Detect ownership first
    for tid in org_ids:
        existing = (await session.execute(
            select(svc.FacingRaion).where(
                svc.FacingRaion.tenant_id == tid, svc.FacingRaion.id == rid,
            )
        )).scalar_one_or_none()
        if existing is not None:
            await svc.update_raion(session, tid, rid, name)
            return OkResponse()
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "error": "Raion inexistent"},
    )


@router.delete("/raioane/{rid}", response_model=OkResponse)
async def api_raion_delete(
    rid: UUID,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    for tid in org_ids:
        existing = (await session.execute(
            select(svc.FacingRaion).where(
                svc.FacingRaion.tenant_id == tid, svc.FacingRaion.id == rid,
            )
        )).scalar_one_or_none()
        if existing is not None:
            await svc.delete_raion(session, tid, rid)
            return OkResponse()
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "error": "Raion inexistent"},
    )


@router.post("/brands", response_model=OkResponse)
async def api_brand_add(
    body: BrandCreateBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Numele este obligatoriu"},
        )
    await svc.add_brand(session, tenant_id, name, body.color)
    return OkResponse()


@router.put("/brands/{bid}", response_model=OkResponse)
async def api_brand_update(
    bid: UUID,
    body: BrandUpdateBody,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Numele este obligatoriu"},
        )
    for tid in org_ids:
        existing = (await session.execute(
            select(svc.FacingBrand).where(
                svc.FacingBrand.tenant_id == tid, svc.FacingBrand.id == bid,
            )
        )).scalar_one_or_none()
        if existing is not None:
            await svc.update_brand(session, tid, bid, name, body.color)
            return OkResponse()
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "error": "Brand inexistent"},
    )


@router.delete("/brands/{bid}", response_model=OkResponse)
async def api_brand_delete(
    bid: UUID,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    for tid in org_ids:
        existing = (await session.execute(
            select(svc.FacingBrand).where(
                svc.FacingBrand.tenant_id == tid, svc.FacingBrand.id == bid,
            )
        )).scalar_one_or_none()
        if existing is not None:
            await svc.delete_brand(session, tid, bid)
            return OkResponse()
    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"ok": False, "error": "Brand inexistent"},
    )


@router.get("/stores", response_model=StoresResponse)
async def api_stores(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    return StoresResponse(stores=await svc.get_stores_by_tenants(session, org_ids))


@router.delete("/store", response_model=StoreDeleteResponse)
async def api_store_delete(
    name: str = Query(...),
    luna: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    name = (name or "").strip()
    if not name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Numele magazinului lipsește"},
        )
    luna_clean = (luna or "").strip() or None
    deleted = 0
    for tid in org_ids:
        deleted += await svc.delete_store_snapshots(
            session, tid,
            name, luna=luna_clean, user=current_user.email or "",
        )
    return StoreDeleteResponse(
        deleted=deleted, store=name, luna=luna_clean,
    )


@router.get("/snapshots", response_model=SnapshotsResponse)
async def api_snapshots(
    store: str | None = Query(None),
    luna: str | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.get_snapshots_by_tenants(
        session, org_ids, store_name=store, luna=luna,
    )
    return SnapshotsResponse(data=data)


@router.post("/save", response_model=SaveResponse)
async def api_save(
    body: SaveBody,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    user = current_user.email or ""
    if not body.entries:
        if not (body.store_name and body.raion_id and body.brand_id and body.luna):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"ok": False, "error": "Date incomplete"},
            )
        await svc.save_snapshot(
            session, tenant_id,
            body.store_name, body.raion_id, body.brand_id, body.luna,
            body.nr_fete or 0, user=user,
        )
        return SaveResponse(saved=1)

    count = await svc.save_bulk(
        session, tenant_id,
        [e.model_dump() for e in body.entries],
        user=user,
    )
    return SaveResponse(saved=count)


@router.get("/evolution", response_model=EvolutionResponse)
async def api_evolution(
    store: str | None = Query(None),
    raion_id: UUID | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.get_evolution_by_tenants(
        session, org_ids,
        store_name=store, raion_id=raion_id,
    )
    return EvolutionResponse(data=data)


@router.get("/dashboard", response_model=DashboardResponse)
async def api_dashboard(
    luna: str | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.get_dashboard_summary_by_tenants(
        session, org_ids, luna=luna,
    )
    return DashboardResponse.model_validate(data)


@router.get("/months", response_model=MonthsResponse)
async def api_months(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    return MonthsResponse(months=await svc.get_available_months_by_tenants(session, org_ids))


@router.get("/raion-competitors", response_model=RaionCompetitorsMatrix)
async def api_raion_competitors_get(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    entries = await svc.get_raion_competitors_matrix_by_tenants(session, org_ids)
    return RaionCompetitorsMatrix(entries=entries)


@router.post("/raion-competitors", response_model=OkResponse)
async def api_raion_competitors_save(
    body: RaionCompetitorsSaveBody,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    await svc.set_raion_competitors_matrix(
        session, tenant_id,
        [e.model_dump() for e in body.entries],
    )
    return OkResponse()


@router.get("/raion-share", response_model=RaionShareResponse)
async def api_raion_share(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    luna: str | None = Query(None, description="YYYY-MM; default = luna cea mai recentă"),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    scope = (scope or "adp").lower()
    if scope not in {"adp", "sika", "sikadp"}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Scope trebuie să fie 'adp', 'sika' sau 'sikadp'"},
        )
    data = await svc.get_raion_share_by_tenants(
        session, org_ids, scope=scope, luna=luna,
    )
    return RaionShareResponse.model_validate(data)
