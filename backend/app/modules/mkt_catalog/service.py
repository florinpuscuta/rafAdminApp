"""
Catalog Lunar — marketing ops.

Port 1:1 din legacy `routes/gallery.py` (gallery_type='catalog') adaptat la
structura SaaS (async, tenant_id, UUID PK, SQLAlchemy 2.0, gallery module).

Folderele reprezintă luni (legacy convenție: „Ianuarie 2026" sau „2026-01").
Păstrăm convenția de parsare `YYYY-MM` din numele folder-ului.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gallery import service as gallery_svc
from app.modules.gallery.models import GalleryFolder, GalleryPhoto

GALLERY_TYPE = "catalog"

# Suportăm formate: „2026-04", „2026_04", „2026/4", și luna română + an
_ISO_RE = re.compile(r"(20\d{2})[-_/](\d{1,2})")
_RO_RE = re.compile(
    r"\b(ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie)\b\s*(20\d{2})",
    re.IGNORECASE,
)
_RO_MONTHS = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4,
    "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
    "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12,
}


def _extract_month(name: str) -> str | None:
    """Extract „YYYY-MM" din numele folder-ului dacă apare.

    Suportă atât format ISO („2026-04") cât și luna RO + an („Aprilie 2026").
    """
    m = _ISO_RE.search(name)
    if m:
        year, month = m.group(1), m.group(2).zfill(2)
        return f"{year}-{month}"
    m = _RO_RE.search(name)
    if m:
        mo = _RO_MONTHS[m.group(1).lower()]
        year = m.group(2)
        return f"{year}-{mo:02d}"
    return None


async def _first_photo(
    session: AsyncSession, tenant_id: UUID, folder_id: UUID
) -> GalleryPhoto | None:
    """Prima poză approved dintr-un folder — folosită drept cover."""
    result = await session.execute(
        select(GalleryPhoto)
        .where(
            GalleryPhoto.tenant_id == tenant_id,
            GalleryPhoto.folder_id == folder_id,
            GalleryPhoto.approval_status == "approved",
        )
        .order_by(GalleryPhoto.uploaded_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_folders_with_cover(
    session: AsyncSession, tenant_id: UUID
) -> list[dict[str, Any]]:
    """Listă foldere catalog, sortate descrescător după lună (sau nume).

    Returnează dict-uri gata de serializare (include cover URL).
    Mirror peste legacy `api_gallery_folders('catalog')` dar cu cover presigned.
    """
    count_subq = (
        select(GalleryPhoto.folder_id, func.count(GalleryPhoto.id).label("n"))
        .where(
            GalleryPhoto.tenant_id == tenant_id,
            GalleryPhoto.approval_status == "approved",
        )
        .group_by(GalleryPhoto.folder_id)
        .subquery()
    )
    stmt = (
        select(GalleryFolder, func.coalesce(count_subq.c.n, 0))
        .outerjoin(count_subq, count_subq.c.folder_id == GalleryFolder.id)
        .where(
            GalleryFolder.tenant_id == tenant_id,
            GalleryFolder.type == GALLERY_TYPE,
        )
    )
    rows = (await session.execute(stmt)).all()

    items: list[dict[str, Any]] = []
    for folder, count in rows:
        cover_url: str | None = None
        if int(count) > 0:
            first = await _first_photo(session, tenant_id, folder.id)
            if first is not None:
                cover_url = gallery_svc.photo_url(first)
        month = _extract_month(folder.name)
        items.append({
            "id": folder.id,
            "name": folder.name,
            "month": month,
            "photo_count": int(count),
            "cover_url": cover_url,
            "created_at": folder.created_at,
        })

    # Sortare: luni recente primele; fallback pe nume desc (legacy: reverse=True)
    def _sort_key(it: dict[str, Any]) -> tuple[int, str]:
        # luni cu month parsabil au prioritate (0), apoi descrescător
        return (0 if it["month"] else 1, it["month"] or "") if it["month"] else (1, it["name"])

    items.sort(key=lambda it: (it["month"] or "~"), reverse=True)
    return items


async def list_photos_for_folder(
    session: AsyncSession, tenant_id: UUID, folder_id: UUID
) -> list[dict[str, Any]]:
    """Poze dintr-un folder catalog — mirror peste `api_gallery_images`."""
    photos = await gallery_svc.list_photos(session, tenant_id, folder_id)
    out: list[dict[str, Any]] = []
    for p in photos:
        url = gallery_svc.photo_url(p)
        out.append({
            "id": p.id,
            "folder_id": p.folder_id,
            "filename": p.filename,
            "size_kb": round(p.size_bytes / 1024, 1),
            "caption": p.caption,
            "uploaded_by_user_id": p.uploaded_by_user_id,
            "uploaded_at": p.uploaded_at,
            "url": url,
            "thumb_url": url,  # fără thumbnail dedicat în SaaS — same URL
        })
    return out


# ── Legacy compat: vechiul placeholder `list_items` (menține tests) ──
async def list_items(session: AsyncSession, tenant_id: UUID) -> dict[str, Any]:
    folders = await list_folders_with_cover(session, tenant_id)
    items = [
        {
            "id": str(f["id"]),
            "title": f["name"],
            "month": f["month"],
        }
        for f in folders
    ]
    notice = None
    if not items:
        notice = 'Nu există încă cataloage — adaugă o lună nouă (buton "+ Lună Nouă").'
    return {"items": items, "notice": notice}
