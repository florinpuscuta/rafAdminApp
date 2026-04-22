"""
Router Panouri & Standuri — endpoint-urile legacy sub prefix-ul SaaS.

Maparea legacy → SaaS (prefix `/api/marketing/panouri`):
  GET    /api/panouri/stores                     → GET    /stores
  GET    /api/panouri/store/{name}               → GET    /store/{name}
  POST   /api/panouri/store/{name}/panel         → POST   /store/{name}/panel
  PUT    /api/panouri/panel/{id}                 → PUT    /panel/{id}
  DELETE /api/panouri/panel/{id}                 → DELETE /panel/{id}
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_user
from app.modules.mkt_panouri import service as svc
from app.modules.mkt_panouri.schemas import (
    AddPanelBody,
    OkResponse,
    PanouStandRow,
    StoreDetailResponse,
    StoresResponse,
    UpdatePanelBody,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/marketing/panouri", tags=["marketing-panouri"])


@router.get("/stores", response_model=StoresResponse)
async def api_stores(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stores = await svc.list_stores(session, current_user.tenant_id)
    return StoresResponse(stores=stores)


@router.get("/store/{store_name:path}", response_model=StoreDetailResponse)
async def api_store_detail(
    store_name: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.get_store_detail(session, current_user.tenant_id, store_name)
    return StoreDetailResponse.model_validate(data)


@router.post("/store/{store_name:path}/panel", response_model=OkResponse)
async def api_add_panel(
    store_name: str,
    body: AddPanelBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await svc.add_panel(
        session, current_user.tenant_id, store_name,
        panel_type=body.panel_type,
        title=body.title,
        width_cm=body.width_cm,
        height_cm=body.height_cm,
        location_in_store=body.location_in_store,
        notes=body.notes,
        created_by=current_user.email or "",
    )
    return OkResponse()


@router.put("/panel/{panel_id}", response_model=OkResponse)
async def api_update_panel(
    panel_id: UUID,
    body: UpdatePanelBody,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"ok": False, "error": "Nimic de actualizat"},
        )
    await svc.update_panel(session, current_user.tenant_id, panel_id, data)
    return OkResponse()


@router.post("/store/{store_name:path}/photos")
async def api_upload_panouri_photos(
    store_name: str,
    images: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Upload multiple photos pentru store. Multipart form-data `images[]`.
    Creează GalleryFolder (type='panouri', name=store_name) dacă lipsește.
    """
    from sqlalchemy import select as _sel
    from app.modules.gallery import service as gallery_service
    from app.modules.gallery.models import GalleryFolder

    # Upsert folder
    folder = (await session.execute(
        _sel(GalleryFolder).where(
            GalleryFolder.tenant_id == current_user.tenant_id,
            GalleryFolder.type == "panouri",
            GalleryFolder.name == store_name,
        )
    )).scalar_one_or_none()
    if folder is None:
        folder = GalleryFolder(
            tenant_id=current_user.tenant_id, type="panouri", name=store_name,
        )
        session.add(folder)
        await session.flush()

    uploaded = 0
    for f in images:
        content = await f.read()
        if not content:
            continue
        await gallery_service.upload_photo(
            session,
            tenant_id=current_user.tenant_id,
            folder=folder,
            filename=f.filename or "photo.jpg",
            content=content,
            content_type=f.content_type or "image/jpeg",
            uploaded_by_user_id=current_user.id,
        )
        uploaded += 1
    return {"ok": True, "uploaded": uploaded}


@router.delete("/panel/{panel_id}", response_model=OkResponse)
async def api_delete_panel(
    panel_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await svc.delete_panel(session, current_user.tenant_id, panel_id)
    return OkResponse()
