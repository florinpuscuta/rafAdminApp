from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ConsolidatTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal  # y2 - y1
    pct: float     # 100 * diff / y1 (0 dacă y1=0)


class ConsolidatAgentRow(APISchema):
    agent_id: UUID | None
    name: str
    stores_count: int
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: float


class ConsolidatStoreRow(APISchema):
    store_id: UUID | None
    name: str
    chain: str | None = None
    city: str | None = None
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: float


class ConsolidatAgentStoresResponse(APISchema):
    agent_id: UUID | None
    company: str
    y1: int
    y2: int
    months: list[int]
    stores: list[ConsolidatStoreRow] = Field(default_factory=list)


class ConsolidatKaResponse(APISchema):
    company: str               # "adeplast" | "sika" | "sikadp"
    company_label: str         # "Adeplast KA", "Sika KA", "SikaDP KA"
    y1: int
    y2: int
    months: list[int]          # [1..N]
    period_label: str          # "YTD — Ian → Apr"
    include_current_month: bool
    totals: ConsolidatTotals
    by_agent: list[ConsolidatAgentRow] = Field(default_factory=list)
