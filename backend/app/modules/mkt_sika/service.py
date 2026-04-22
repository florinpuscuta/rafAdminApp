"""
Service "Acțiuni SIKA" — port 1:1 al logicii din `adeplast-dashboard`:
  - Text liber salvat în `marketing_actions` (upsert tenant × scope × y × m).
  - Poze stocate via modulul `gallery` (folder type='sika', name='YYYY-MM').
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gallery import service as gallery_svc
from app.modules.gallery.models import GalleryFolder, GalleryPhoto
from app.modules.mkt_sika.models import MarketingAction

logger = logging.getLogger(__name__)

GALLERY_TYPE = "sika"

_MONTH_NAMES = {
    1: "Ianuarie", 2: "Februarie", 3: "Martie", 4: "Aprilie",
    5: "Mai", 6: "Iunie", 7: "Iulie", 8: "August",
    9: "Septembrie", 10: "Octombrie", 11: "Noiembrie", 12: "Decembrie",
}

# Legacy: uploads/actiuni_sika/2026-04/... — păstrăm aceeași convenție
# pentru `name` al folder-ului din gallery.
_FOLDER_NAME_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def month_name(m: int) -> str:
    return _MONTH_NAMES.get(m, str(m))


def folder_name_for(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


# ── Text liber ──

def _action_to_dict(
    row: MarketingAction | None, *, scope: str, year: int, month: int,
) -> dict[str, Any]:
    if row is None:
        return {
            "scope": scope,
            "year": year,
            "month": month,
            "month_name": month_name(month),
            "content": "",
            "updated_by": None,
            "updated_at": None,
        }
    return {
        "scope": row.scope,
        "year": row.year,
        "month": row.month,
        "month_name": month_name(row.month),
        "content": row.content,
        "updated_by": row.updated_by,
        "updated_at": row.updated_at,
    }


async def get_action(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year: int,
    month: int,
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(MarketingAction).where(
                MarketingAction.tenant_id == tenant_id,
                MarketingAction.scope == scope,
                MarketingAction.year == year,
                MarketingAction.month == month,
            )
        )
    ).scalar_one_or_none()
    return _action_to_dict(row, scope=scope, year=year, month=month)


async def save_action(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year: int,
    month: int,
    content: str,
    updated_by: str | None = None,
    updated_by_user_id: UUID | None = None,
) -> dict[str, Any]:
    existing = (
        await session.execute(
            select(MarketingAction).where(
                MarketingAction.tenant_id == tenant_id,
                MarketingAction.scope == scope,
                MarketingAction.year == year,
                MarketingAction.month == month,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        row = MarketingAction(
            tenant_id=tenant_id,
            scope=scope,
            year=year,
            month=month,
            content=content,
            updated_by=updated_by,
            updated_by_user_id=updated_by_user_id,
        )
        session.add(row)
    else:
        existing.content = content
        existing.updated_by = updated_by
        existing.updated_by_user_id = updated_by_user_id
        row = existing

    await session.commit()
    await session.refresh(row)
    logger.info(
        "mkt_sika.action.save tenant=%s scope=%s %s/%s len=%d by=%s",
        tenant_id, scope, year, month, len(content), updated_by,
    )
    return _action_to_dict(row, scope=scope, year=year, month=month)


# ── Poze (gallery) ──

async def _get_or_create_folder(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> GalleryFolder:
    """Găsește sau creează folderul gallery pentru luna respectivă."""
    name = folder_name_for(year, month)
    folders = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)
    for f, _count in folders:
        if f.name == name:
            return f
    return await gallery_svc.create_folder(
        session, tenant_id=tenant_id, type_=GALLERY_TYPE, name=name,
    )


async def _get_folder(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> GalleryFolder | None:
    name = folder_name_for(year, month)
    folders = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)
    for f, _count in folders:
        if f.name == name:
            return f
    return None


def _photo_to_dict(photo: GalleryPhoto) -> dict[str, Any]:
    url = gallery_svc.photo_url(photo)
    return {
        "id": photo.id,
        "filename": photo.filename,
        "url": url,
        "thumb": url,  # legacy avea thumbs separate; cu MinIO presigned URL-ul merge pe ambele
        "uploaded_by": None,
        "uploaded_at": photo.uploaded_at,
    }


async def list_photos(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> list[dict[str, Any]]:
    folder = await _get_folder(session, tenant_id, year=year, month=month)
    if folder is None:
        return []
    photos = await gallery_svc.list_photos(session, tenant_id, folder.id)
    # Legacy sorta alfabetic pe filename ascendent (sorted(os.listdir(...))).
    photos_sorted = sorted(photos, key=lambda p: p.filename.lower())
    return [_photo_to_dict(p) for p in photos_sorted]


async def upload_photos(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int,
    month: int,
    files: list[tuple[str, bytes, str]],  # (filename, content, content_type)
    uploaded_by_user_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Upload 1..N poze. Returnează doar cele salvate cu succes (legacy
    sărea tăcut peste extensii invalide — aici returnăm doar ce s-a salvat)."""
    folder = await _get_or_create_folder(
        session, tenant_id, year=year, month=month,
    )
    saved: list[dict[str, Any]] = []
    for filename, content, content_type in files:
        photo = await gallery_svc.upload_photo(
            session,
            tenant_id=tenant_id,
            folder=folder,
            filename=filename,
            content=content,
            content_type=content_type,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        saved.append(_photo_to_dict(photo))
    return saved


async def delete_photo(
    session: AsyncSession, tenant_id: UUID, *, photo_id: UUID,
) -> bool:
    photo = await gallery_svc.get_photo(session, tenant_id, photo_id)
    if photo is None:
        return False
    await gallery_svc.delete_photo(session, photo)
    return True


async def rotate_photo(
    session: AsyncSession, tenant_id: UUID, *, photo_id: UUID,
) -> dict[str, Any] | None:
    """Rotește o poză 90° clockwise — mirror legacy `api_actiuni_sika_photos_rotate`.

    Necesită Pillow. Dacă nu e instalat, endpoint-ul va întoarce None și
    router-ul va răspunde 501 Not Implemented.
    """
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        logger.warning("mkt_sika.rotate: Pillow nu e instalat")
        return None

    photo = await gallery_svc.get_photo(session, tenant_id, photo_id)
    if photo is None:
        return None

    # Descarcă din MinIO → rotește → re-uploadează (overwrite object_key).
    from app.core import storage
    data = storage.get_object_bytes(photo.object_key)
    img = Image.open(io.BytesIO(data))
    img = img.rotate(-90, expand=True)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)
    new_bytes = buf.getvalue()

    storage.put_object(photo.object_key, new_bytes, "image/jpeg")
    # Actualizează metadata relevantă (dimensiune / content_type JPEG).
    photo.size_bytes = len(new_bytes)
    photo.content_type = "image/jpeg"
    await session.commit()
    await session.refresh(photo)
    return _photo_to_dict(photo)


# ── Placeholder legacy pentru compatibilitate (endpoint `GET /api/marketing/sika`). ──

async def list_items(session: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    folders = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)
    items = []
    for folder, photo_count in folders:
        luna = folder.name if _FOLDER_NAME_RE.match(folder.name) else None
        items.append({
            "id": str(folder.id),
            "title": folder.name,
            "luna": luna,
            "notes": f"{photo_count} poze",
        })
    notice = None
    if not items:
        notice = "Nu există încă acțiuni SIKA."
    return {"items": items, "notice": notice}
