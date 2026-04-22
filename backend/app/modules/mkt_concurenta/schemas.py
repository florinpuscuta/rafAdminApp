"""
Schemas pentru Acțiuni Concurență.

Oglindă 1:1 a feature-ului legacy `renderConcurenta` din adeplast-dashboard:
- grid cu 12 luni pe an, cover + count
- modal cu lista de poze per lună
- upload multi-file + delete + rotate

Stocare: folosim modulul `gallery` cu `type='concurenta'` și nume folder
`YYYY_MM` (același format ca legacy — vezi `templates/index.html:12853`).
"""
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ConcurentaMonthCell(APISchema):
    """O celulă din grid (o lună dintr-un an)."""

    month: int  # 1..12
    folder_key: str  # "YYYY_MM"
    label: str  # „Ianuarie" etc.
    folder_id: UUID | None = None  # null dacă nu există folder încă
    count: int = 0
    cover_url: str | None = None
    is_future: bool = False


class ConcurentaYearResponse(APISchema):
    """Răspunsul /api/marketing/concurenta?year=YYYY."""

    year: int
    cells: list[ConcurentaMonthCell] = Field(default_factory=list)


class ConcurentaFolderEnsureRequest(APISchema):
    """Cerere pentru a asigura folder-ul unei luni (creează dacă nu există)."""

    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class ConcurentaFolderOut(APISchema):
    """Folder concurență (wrapper peste GalleryFolder)."""

    id: UUID
    folder_key: str  # "YYYY_MM"
    year: int
    month: int
    created_at: datetime


class ConcurentaPhotoOut(APISchema):
    """Poză din folderul concurență — oglindă parțială a `PhotoOut` din gallery."""

    id: UUID
    folder_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    caption: str | None
    uploaded_at: datetime
    url: str
    thumb_url: str  # în lipsa thumb-urilor, aceeași ca `url`


class ConcurentaPhotosResponse(APISchema):
    folder_key: str
    folder_id: UUID
    images: list[ConcurentaPhotoOut] = Field(default_factory=list)


class ConcurentaUploadResponse(APISchema):
    uploaded: int
    errors: list[str] = Field(default_factory=list)
    folder_id: UUID
