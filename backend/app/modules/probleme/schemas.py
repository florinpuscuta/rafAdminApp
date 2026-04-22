"""
Schemas pentru "Probleme în Activitate".

Legacy: tabel `activity_problems` (year, month, content, updated_by,
updated_at) + un feed de poze atașate via `gallery_photos`.

În SaaS: TODO — migrare Alembic pentru `activity_problems`. Până atunci
serviciul întoarce conținut gol per perioadă.
"""
from datetime import datetime
from uuid import UUID

from app.core.schemas import APISchema


class ProblemePhoto(APISchema):
    id: UUID
    url: str
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None


class ProblemeResponse(APISchema):
    scope: str                # "adp" | "sika" | "sikadp"
    year: int
    month: int
    month_name: str
    content: str = ""
    updated_by: str | None = None
    updated_at: datetime | None = None
    photos: list[ProblemePhoto] = []
    todo: str | None = None


class ProblemeSaveRequest(APISchema):
    scope: str = "adp"
    year: int
    month: int
    content: str
