"""
Schemas pentru Foaia de Parcurs.

Legacy:
  - POST /api/parcurs/generate  (AI-powered route generation)
  - GET  /api/parcurs/agents
  - GET  /api/parcurs/stores/<agent>

În SaaS canonical, agenții + magazinele vin din tabelele proprii; generarea
efectivă AI nu e portată încă (TODO). Schema curentă acoperă structura
răspunsului legacy pentru a permite UI-ul.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.core.schemas import APISchema


class ParcursAgentOption(APISchema):
    agent_id: UUID | None
    agent_name: str
    stores_count: int


class ParcursStoreOption(APISchema):
    store_id: UUID | None
    store_name: str
    city: str | None = None


class ParcursFuelFill(APISchema):
    date: str              # "YYYY-MM-DD"
    liters: float
    cost: float


class ParcursGenerateRequest(APISchema):
    scope: str = "adp"     # "adp" | "sika" | "sikadp"
    agent: str
    year: int
    month: int
    km_start: int
    km_end: int
    car_number: str | None = None
    sediu: str = "Oradea"
    fuel_fills: list[ParcursFuelFill] = []
    ai_provider: str | None = None   # "deepseek"|"anthropic"|"openai"
    ai_key: str | None = None


class ParcursEntry(APISchema):
    date: str              # "DD.MM.YYYY"
    day_name: str
    route: str
    stores_visited: list[str] = []
    km_start: int
    km_end: int
    km_driven: int
    purpose: str
    fuel_liters: float | None = None
    fuel_cost: float | None = None


class ParcursResponse(APISchema):
    agent: str
    month: int
    month_name: str
    year: int
    car_number: str | None = None
    sediu: str
    km_start: int
    km_end: int
    total_km: int
    working_days: int
    avg_km_per_day: float
    total_fuel_liters: float
    total_fuel_cost: float
    ai_generated: bool = False
    entries: list[ParcursEntry] = []
    fuel_fills: list[ParcursFuelFill] = []
    todo: str | None = None


class ParcursAgentsResponse(APISchema):
    scope: str
    agents: list[ParcursAgentOption] = []


class ParcursStoresResponse(APISchema):
    scope: str
    agent: str
    stores: list[ParcursStoreOption] = []


class ParcursSheetSummary(APISchema):
    id: UUID
    agent_name: str
    year: int
    month: int
    month_name: str
    total_km: int
    working_days: int
    updated_at: datetime


class ParcursSheetsListResponse(APISchema):
    scope: str
    sheets: list[ParcursSheetSummary] = []
