"""
Schemas pentru "Activitate Agenți" — raport activitate teren per agent pe
interval de date.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.core.schemas import APISchema


class ActivitateVisitRow(APISchema):
    """O vizită individuală (check-in la magazin)."""

    visit_date: date
    store_id: UUID | None = None
    store_name: str
    client: str | None = None
    check_in: str | None = None   # HH:MM sau ISO timestamp
    check_out: str | None = None
    duration_min: int | None = None
    km: Decimal | None = None
    notes: str | None = None
    photos_count: int = 0


class ActivitateAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str
    visits_count: int
    stores_count: int
    total_km: Decimal
    total_duration_min: int
    visits: list[ActivitateVisitRow] = []


class ActivitateResponse(APISchema):
    scope: str                        # "adp" | "sika" | "sikadp"
    date_from: date
    date_to: date
    agents_count: int
    total_visits: int
    total_stores: int
    total_km: Decimal
    agents: list[ActivitateAgentRow] = []
    todo: str | None = None


class ActivitateVisitCreate(APISchema):
    """Payload pentru POST /api/activitate/visits."""

    scope: str = "adp"
    visit_date: date
    agent_id: UUID | None = None
    store_id: UUID | None = None
    client: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    duration_min: int | None = None
    km: Decimal | None = None
    notes: str | None = None


class ActivitateVisitCreated(APISchema):
    id: UUID
    visit_date: date
    agent_id: UUID | None
    store_id: UUID | None
