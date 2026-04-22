"""
Schemas pentru Panouri & Standuri — oglindesc shape-urile endpoint-urilor
legacy `/api/panouri/*`. APISchema convertește snake_case → camelCase.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class PanouStandRow(APISchema):
    id: UUID
    store_name: str
    panel_type: str
    title: str | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    location_in_store: str | None = None
    notes: str | None = None
    photo_filename: str | None = None
    photo_thumb: str | None = None
    agent: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PhotoRow(APISchema):
    id: UUID | None = None
    filename: str
    url: str
    thumb_url: str | None = None
    size_kb: float = 0
    notes: str | None = None
    photo_date: str | None = None
    uploaded_by: str | None = None
    category: str | None = None


class StoreListItem(APISchema):
    name: str
    agent: str = ""
    client: str = ""
    ship_to: str = ""
    panel_count: int = 0
    photo_count: int = 0


class StoresResponse(APISchema):
    ok: bool = True
    stores: list[StoreListItem] = Field(default_factory=list)


class StoreDetailResponse(APISchema):
    ok: bool = True
    store: str
    panels: list[PanouStandRow] = Field(default_factory=list)
    photos: list[PhotoRow] = Field(default_factory=list)


class AddPanelBody(APISchema):
    panel_type: str = "panou"
    title: str = ""
    width_cm: float | None = None
    height_cm: float | None = None
    location_in_store: str = ""
    notes: str = ""


class UpdatePanelBody(APISchema):
    panel_type: str | None = None
    title: str | None = None
    width_cm: float | None = None
    height_cm: float | None = None
    location_in_store: str | None = None
    notes: str | None = None


class OkResponse(APISchema):
    ok: bool = True
    error: str | None = None
