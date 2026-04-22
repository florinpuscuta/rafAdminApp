from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class VzKpis(APISchema):
    prev_sales: Decimal
    curr_sales: Decimal
    nelivrate: Decimal
    nefacturate: Decimal
    orders_total: Decimal
    exercitiu: Decimal
    gap: Decimal  # exercitiu - prev_sales (+ = overachievement, - = deficit)


class VzStoreRow(APISchema):
    store_id: UUID | None
    store_name: str
    prev_sales: Decimal
    curr_sales: Decimal
    nelivrate: Decimal
    nefacturate: Decimal
    orders_total: Decimal
    exercitiu: Decimal


class VzAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str
    stores_count: int
    prev_sales: Decimal
    curr_sales: Decimal
    nelivrate: Decimal
    nefacturate: Decimal
    orders_total: Decimal
    exercitiu: Decimal
    stores: list[VzStoreRow] = Field(default_factory=list)


class VzScopeBlock(APISchema):
    """Minimal per-scope block (used in SIKADP sub-sections)."""
    kpis: VzKpis
    report_date: date | None = None
    ind_processed: int | None = None
    ind_missing: int | None = None
    ind_processed_amount: Decimal | None = None
    ind_missing_amount: Decimal | None = None


class VzResponse(APISchema):
    scope: str                    # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    month: int
    month_name: str
    last_update: datetime | None = None

    # populated for adp / sika
    report_date: date | None = None
    kpis: VzKpis | None = None
    agents: list[VzAgentRow] = Field(default_factory=list)

    # adp-only extras
    ind_processed: int | None = None
    ind_missing: int | None = None
    ind_processed_amount: Decimal | None = None
    ind_missing_amount: Decimal | None = None

    # populated for sikadp
    combined: "VzCombinedBlock | None" = None
    adeplast: VzScopeBlock | None = None
    sika: VzScopeBlock | None = None


class VzCombinedBlock(APISchema):
    kpis: VzKpis
    agents: list[VzAgentRow] = Field(default_factory=list)


VzResponse.model_rebuild()
