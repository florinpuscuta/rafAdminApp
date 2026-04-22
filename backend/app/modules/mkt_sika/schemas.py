"""
Schemas pentru "Acțiuni SIKA" (marketing).

Port 1:1 al payload-urilor din `adeplast-dashboard/routes/sales.py`:
  - GET  /api/marketing_actions/<year>/<month>       → {content, updated_by, updated_at}
  - POST /api/marketing_actions/<year>/<month>       → {ok: True}
  - GET  /api/actiuni_sika/<year>/<month>/photos     → {photos: [...]}
  - POST /api/actiuni_sika/<year>/<month>/photos     → {ok, saved, count}
  - DELETE /api/actiuni_sika/.../photos/<filename>   → {ok}
  - POST /api/actiuni_sika/.../photos/<filename>/rotate → {ok}

În SaaS unificăm totul sub `/api/marketing/sika/{year}/{month}` + endpoint-uri
de poze cu același shape, dar `filename` devine UUID-ul pozei din gallery
(stabile, nu depind de numele fișierului uploadat).
"""
from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


# ── Text liber (acțiuni programate) ──

class MktSikaActionResponse(APISchema):
    """Răspunsul pentru GET /api/marketing/sika/{year}/{month}."""
    scope: str                # "sika" (default) | "adp" | "sikadp"
    year: int
    month: int
    month_name: str
    content: str = ""
    updated_by: str | None = None
    updated_at: datetime | None = None


class MktSikaActionSaveRequest(APISchema):
    scope: str = "sika"
    content: str


# ── Poze (gallery-backed, folder type='sika' / name='YYYY-MM') ──

class MktSikaPhoto(APISchema):
    id: UUID
    filename: str
    url: str
    thumb: str          # momentan = url (MinIO nu generează thumbnails separat)
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None


class MktSikaPhotosResponse(APISchema):
    photos: list[MktSikaPhoto] = Field(default_factory=list)


class MktSikaPhotoUploadResponse(APISchema):
    """Mirror legacy: {ok, saved: [...], count}."""
    ok: bool = True
    saved: list[MktSikaPhoto] = Field(default_factory=list)
    count: int = 0


class MktSikaOkResponse(APISchema):
    """Mirror legacy: {ok: True}."""
    ok: bool = True


# ── Placeholder legacy (listă de acțiuni pe toată perioada — păstrat
#    pt. compatibilitate cu scheletul existent; neutilizat de UI-ul portat) ──

class MktSikaItem(APISchema):
    id: str
    title: str
    luna: str | None = None  # "YYYY-MM"
    notes: str | None = None


class MktSikaResponse(APISchema):
    items: list[MktSikaItem] = Field(default_factory=list)
    notice: str | None = None
