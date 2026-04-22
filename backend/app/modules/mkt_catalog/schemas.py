"""Schemas pentru Catalog Lunar — mirror 1:1 peste Gallery (type='catalog')."""
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class CatalogFolderOut(APISchema):
    """Un folder de catalog — o lună (ex: „Ianuarie 2026" sau „2026-01")."""

    id: UUID
    name: str
    month: str | None = None  # „YYYY-MM" extras din name, None dacă nu matchează
    photo_count: int = 0
    cover_url: str | None = None  # presigned URL pentru prima poză, pentru cover
    created_at: datetime


class CatalogFolderListResponse(APISchema):
    """Răspunsul /api/marketing/catalog — lista de foldere."""

    folders: list[CatalogFolderOut] = Field(default_factory=list)
    notice: str | None = None


class CreateCatalogFolderRequest(APISchema):
    """Numele de folder — convenție legacy: „Luna AAAA" sau „YYYY-MM"."""

    name: str = Field(min_length=1, max_length=200)


class CatalogPhotoOut(APISchema):
    id: UUID
    folder_id: UUID
    filename: str
    size_kb: float
    caption: str | None
    uploaded_by_user_id: UUID | None
    uploaded_at: datetime
    url: str  # presigned URL
    thumb_url: str  # la fel, fără thumbnail dedicat în SaaS


class CatalogFolderDetailResponse(APISchema):
    """Detaliu folder = lista de poze."""

    folder_id: UUID
    folder_name: str
    month: str | None = None
    photos: list[CatalogPhotoOut] = Field(default_factory=list)


# ── Legacy-compat (place-holder pentru ecranul vechi `MktCatalogResponse`) ──
class MktCatalogItem(APISchema):
    id: str
    title: str
    month: str | None = None


class MktCatalogResponse(APISchema):
    """Răspuns compatibil cu vechiul placeholder (menține tests existente)."""

    items: list[MktCatalogItem] = Field(default_factory=list)
    notice: str | None = None
