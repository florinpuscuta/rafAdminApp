"""
Acțiuni Concurență — marketing ops.

Port 1:1 al feature-ului legacy `renderConcurenta` din
adeplast-dashboard/templates/index.html (~line 12811).

Stocare: gallery module, `type='concurenta'`. Un folder per lună, nume
`YYYY_MM` (exact ca legacy — vezi `uploads/sikadp/concurenta/2026_03/`).

Conceptual:
  legacy: /uploads/sikadp/concurenta/YYYY_MM/ + thumb_*.jpg
  SaaS:   gallery_folder(type='concurenta', name='YYYY_MM') + MinIO photos
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gallery import service as gallery_svc
from app.modules.gallery.models import GalleryFolder, GalleryPhoto

GALLERY_TYPE = "concurenta"

# Oglinda exactă a `MONTH_LABELS_FULL` din templates/index.html:12813
MONTH_LABELS_FULL = [
    "",
    "Ianuarie",
    "Februarie",
    "Martie",
    "Aprilie",
    "Mai",
    "Iunie",
    "Iulie",
    "August",
    "Septembrie",
    "Octombrie",
    "Noiembrie",
    "Decembrie",
]

_FOLDER_KEY_RE = re.compile(r"^(20\d{2})_(0[1-9]|1[0-2])$")


def _folder_key(year: int, month: int) -> str:
    """„YYYY_MM" — format identic cu legacy (`${year}_${String(m).padStart(2,'0')}`)."""
    return f"{year}_{month:02d}"


def _parse_folder_key(name: str) -> tuple[int, int] | None:
    m = _FOLDER_KEY_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


async def list_year(
    session: AsyncSession, tenant_id: UUID, year: int
) -> dict[str, Any]:
    """
    Grid de 12 luni pentru un an.

    Oglinda buclei `for (let m = 1; m <= 12; m++)` din legacy:
      - dacă folder există → count + cover (primul file); altfel count=0, cover=null
      - `is_future = year > curYear || (year == curYear && m > curMonth)`
    """
    now = datetime.now()
    cur_year, cur_month = now.year, now.month

    pairs = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)

    # Map "YYYY_MM" -> (folder, count)
    folder_map: dict[str, tuple[GalleryFolder, int]] = {}
    for folder, count in pairs:
        parsed = _parse_folder_key(folder.name)
        if parsed is None:
            continue
        fy, fm = parsed
        if fy == year:
            folder_map[folder.name] = (folder, count)

    cells: list[dict[str, Any]] = []
    for m in range(1, 13):
        key = _folder_key(year, m)
        pair = folder_map.get(key)
        folder_id: UUID | None = None
        count = 0
        cover_url: str | None = None
        if pair is not None:
            folder, count = pair
            folder_id = folder.id
            # Cover = primul file sortat alfabetic (legacy: `sorted(imgs)[0]`)
            photos = await gallery_svc.list_photos(session, tenant_id, folder.id)
            if photos:
                first = sorted(photos, key=lambda p: p.filename)[0]
                cover_url = gallery_svc.photo_url(first)
        is_future = year > cur_year or (year == cur_year and m > cur_month)
        cells.append(
            {
                "month": m,
                "folder_key": key,
                "label": MONTH_LABELS_FULL[m],
                "folder_id": folder_id,
                "count": count,
                "cover_url": cover_url,
                "is_future": is_future,
            }
        )

    return {"year": year, "cells": cells}


async def ensure_folder(
    session: AsyncSession, tenant_id: UUID, year: int, month: int
) -> GalleryFolder:
    """Creează folder `YYYY_MM` dacă nu există; idempotent."""
    key = _folder_key(year, month)
    # Căutăm explicit după nume
    pairs = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)
    for folder, _ in pairs:
        if folder.name == key:
            return folder
    return await gallery_svc.create_folder(
        session, tenant_id=tenant_id, type_=GALLERY_TYPE, name=key
    )


async def get_folder_by_key(
    session: AsyncSession, tenant_id: UUID, folder_key: str
) -> GalleryFolder | None:
    """Rezolvă folder după „YYYY_MM"."""
    if _parse_folder_key(folder_key) is None:
        return None
    pairs = await gallery_svc.list_folders(session, tenant_id, type_=GALLERY_TYPE)
    for folder, _ in pairs:
        if folder.name == folder_key:
            return folder
    return None


async def list_photos(
    session: AsyncSession, tenant_id: UUID, folder: GalleryFolder
) -> list[GalleryPhoto]:
    """
    Poze sortate după `filename` (legacy: `sorted(os.listdir(folder_path))`).
    """
    photos = await gallery_svc.list_photos(session, tenant_id, folder.id)
    photos.sort(key=lambda p: p.filename)
    return photos
