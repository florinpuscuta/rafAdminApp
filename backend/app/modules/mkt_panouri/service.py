"""
Service Panouri & Standuri — port 1:1 al logicii din
`adeplast-dashboard/routes/gallery.py` (secțiunea `# ── Panouri & Standuri ──`).

Endpoint-urile legacy portate:
  GET    /api/panouri/stores              → list_stores
  GET    /api/panouri/store/{name}        → get_store_detail
  POST   /api/panouri/store/{name}/panel  → add_panel
  PUT    /api/panouri/panel/{id}          → update_panel
  DELETE /api/panouri/panel/{id}          → delete_panel

Sursa magazinelor: `store_agent_mappings.cheie_finala` — echivalent SaaS cu
`unified_store_agent_map` din legacy (dedupe pe cheie_finala).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.modules.gallery.models import GalleryFolder, GalleryPhoto
from app.modules.mappings.models import StoreAgentMapping
from app.modules.mkt_panouri.models import PanouStand


async def list_stores(
    session: AsyncSession, tenant_id: UUID,
) -> list[dict[str, Any]]:
    return await list_stores_by_tenants(session, [tenant_id])


async def list_stores_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[dict[str, Any]]:
    """Lista magazine KA (cheie_finala) + panel_count per magazin (multi-org)."""
    if not tenant_ids:
        return []
    store_rows = (await session.execute(
        select(
            StoreAgentMapping.cheie_finala,
            StoreAgentMapping.agent_unificat,
            StoreAgentMapping.client_original,
            StoreAgentMapping.ship_to_original,
        )
        .where(
            StoreAgentMapping.tenant_id.in_(tenant_ids),
            StoreAgentMapping.cheie_finala.is_not(None),
            StoreAgentMapping.cheie_finala != "",
            ~func.upper(StoreAgentMapping.client_original).like("%PUSKIN%"),
            ~StoreAgentMapping.cheie_finala.like("%|%"),
        )
        .order_by(StoreAgentMapping.cheie_finala)
    )).all()

    seen: set[str] = set()
    stores: list[dict[str, Any]] = []
    for cf, ag, cl, st in store_rows:
        if cf in seen:
            continue
        seen.add(cf)
        stores.append({
            "name": cf,
            "agent": ag or "",
            "client": cl or "",
            "ship_to": st or "",
        })

    # Panel count per store — agregat cross-tenant.
    count_rows = (await session.execute(
        select(PanouStand.store_name, func.count(PanouStand.id))
        .where(PanouStand.tenant_id.in_(tenant_ids))
        .group_by(PanouStand.store_name)
    )).all()
    counts: dict[str, int] = {}
    for r in count_rows:
        counts[r[0]] = counts.get(r[0], 0) + int(r[1] or 0)

    # Photo count per store — din gallery (type='panouri', name=store_name). Doar approved.
    photo_rows = (await session.execute(
        select(GalleryFolder.name, func.count(GalleryPhoto.id))
        .join(GalleryPhoto, GalleryPhoto.folder_id == GalleryFolder.id)
        .where(
            GalleryFolder.tenant_id.in_(tenant_ids),
            GalleryFolder.type == "panouri",
            GalleryPhoto.approval_status == "approved",
        )
        .group_by(GalleryFolder.name)
    )).all()
    photo_counts: dict[str, int] = {}
    for r in photo_rows:
        photo_counts[r[0]] = photo_counts.get(r[0], 0) + int(r[1] or 0)

    for s in stores:
        s["panel_count"] = counts.get(s["name"], 0)
        s["photo_count"] = photo_counts.get(s["name"], 0)
    return stores


async def get_store_detail(
    session: AsyncSession, tenant_id: UUID, store_name: str,
) -> dict[str, Any]:
    return await get_store_detail_by_tenants(session, [tenant_id], store_name)


async def get_store_detail_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID], store_name: str,
) -> dict[str, Any]:
    """Port al `api_panouri_store_detail` din `gallery.py:518` (multi-org)."""
    if not tenant_ids:
        return {"store": store_name, "panels": [], "photos": []}
    rows = (await session.execute(
        select(PanouStand)
        .where(
            PanouStand.tenant_id.in_(tenant_ids),
            PanouStand.store_name == store_name,
        )
        .order_by(PanouStand.panel_type, PanouStand.title)
    )).scalars().all()

    panels = [
        {
            "id": p.id,
            "store_name": p.store_name,
            "panel_type": p.panel_type,
            "title": p.title,
            "width_cm": p.width_cm,
            "height_cm": p.height_cm,
            "location_in_store": p.location_in_store,
            "notes": p.notes,
            "photo_filename": p.photo_filename,
            "photo_thumb": p.photo_thumb,
            "agent": p.agent,
            "created_by": p.created_by,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in rows
    ]

    # Fotografii din gallery_photos (type='panouri', name=store_name). Doar approved.
    photo_rows = (await session.execute(
        select(
            GalleryPhoto.id, GalleryPhoto.filename, GalleryPhoto.object_key,
            GalleryPhoto.size_bytes, GalleryPhoto.caption, GalleryPhoto.uploaded_at,
        )
        .join(GalleryFolder, GalleryFolder.id == GalleryPhoto.folder_id)
        .where(
            GalleryPhoto.tenant_id.in_(tenant_ids),
            GalleryFolder.type == "panouri",
            GalleryFolder.name == store_name,
            GalleryPhoto.approval_status == "approved",
        )
        .order_by(GalleryPhoto.uploaded_at.desc())
    )).all()

    photos = []
    for p in photo_rows:
        # Proxy prin backend — evită signature/host issues cu MinIO.
        url = f"/api/gallery/photos/{p.id}/raw"
        photos.append({
            "id": p.id,
            "filename": p.filename,
            "url": url,
            "thumb_url": url,
            "size_kb": round((p.size_bytes or 0) / 1024, 1),
            "notes": p.caption,
            "photo_date": p.uploaded_at.strftime("%Y-%m-%d") if p.uploaded_at else None,
            "uploaded_by": None,
            "category": None,
        })
    return {"store": store_name, "panels": panels, "photos": photos}


async def add_panel(
    session: AsyncSession, tenant_id: UUID, store_name: str,
    *,
    panel_type: str = "panou",
    title: str = "",
    width_cm: float | None = None,
    height_cm: float | None = None,
    location_in_store: str = "",
    notes: str = "",
    created_by: str = "",
) -> PanouStand:
    """Port al `api_panouri_add_panel` din `gallery.py:578`."""
    try:
        width_cm = float(width_cm) if width_cm else None
    except (ValueError, TypeError):
        width_cm = None
    try:
        height_cm = float(height_cm) if height_cm else None
    except (ValueError, TypeError):
        height_cm = None

    p = PanouStand(
        tenant_id=tenant_id,
        store_name=store_name,
        panel_type=panel_type or "panou",
        title=title.strip() or None,
        width_cm=width_cm,
        height_cm=height_cm,
        location_in_store=(location_in_store or "").strip() or None,
        notes=(notes or "").strip() or None,
        created_by=created_by or None,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def update_panel(
    session: AsyncSession, tenant_id: UUID, panel_id: UUID,
    data: dict[str, Any],
) -> PanouStand | None:
    """Port al `api_panouri_update_panel` din `gallery.py:608`."""
    fields = ["panel_type", "title", "width_cm", "height_cm", "location_in_store", "notes"]
    vals: dict[str, Any] = {}
    for f in fields:
        if f in data:
            val = data[f]
            if f in ("width_cm", "height_cm"):
                try:
                    val = float(val) if val else None
                except (ValueError, TypeError):
                    val = None
            vals[f] = val
    if not vals:
        return None
    vals["updated_at"] = datetime.utcnow()
    await session.execute(
        update(PanouStand)
        .where(PanouStand.tenant_id == tenant_id, PanouStand.id == panel_id)
        .values(**vals)
    )
    await session.commit()
    return (await session.execute(
        select(PanouStand).where(
            PanouStand.tenant_id == tenant_id, PanouStand.id == panel_id,
        )
    )).scalar_one_or_none()


async def delete_panel(
    session: AsyncSession, tenant_id: UUID, panel_id: UUID,
) -> bool:
    """Port al `api_panouri_delete_panel` din `gallery.py:636`."""
    res = await session.execute(
        delete(PanouStand).where(
            PanouStand.tenant_id == tenant_id, PanouStand.id == panel_id,
        )
    )
    await session.commit()
    return (res.rowcount or 0) > 0
