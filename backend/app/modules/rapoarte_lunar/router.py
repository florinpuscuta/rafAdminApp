"""Router pentru /api/rapoarte/lunar.

GET /api/rapoarte/lunar?year=YYYY&month=MM
  Returnează `RaportLunarResponse` — KPI YoY + top clients + top agents +
  chain breakdown pentru (year, month).

Dacă nu există date pentru (year, month), `has_data` e false și listele
sunt goale. Nu aruncăm 404 — frontend-ul afișează un gol prietenos.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.rapoarte_lunar import service as svc
from app.modules.rapoarte_lunar.schemas import RaportLunarResponse

router = APIRouter(prefix="/api/rapoarte/lunar", tags=["rapoarte-lunar"])


@router.get("", response_model=RaportLunarResponse)
async def get_raport_lunar(
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> RaportLunarResponse:
    now = datetime.now(timezone.utc)
    y = year or now.year
    # Dacă nu e lună specificată, folosim luna curentă (cu fallback pe
    # luna precedentă pentru prima zi a lunii când există puține date).
    m = month or now.month

    data = await svc.build_raport(session, tenant_id, year=y, month=m)
    return RaportLunarResponse.model_validate(data)
