from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class ApLYearTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class ApLMonthCell(APISchema):
    month: int                          # 1..12
    month_name: str                     # "Ianuarie"..."Decembrie"
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class ApLAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str
    months: list[ApLMonthCell] = Field(default_factory=list)  # 12 items
    totals: ApLYearTotals


class ApLMonthTotal(APISchema):
    """Total pe toți agenții pentru o lună."""
    month: int
    month_name: str
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class ApLResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    agents: list[ApLAgentRow] = Field(default_factory=list)
    month_totals: list[ApLMonthTotal] = Field(default_factory=list)
    grand_totals: ApLYearTotals
