from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class TgtMonthCell(APISchema):
    month: int                          # 1..12
    month_name: str                     # "Ianuarie"..."Decembrie"
    prev_sales: Decimal                 # an referință
    curr_sales: Decimal                 # realizat an curent
    target: Decimal                     # prev × (1 + pct/100)
    target_pct: Decimal                 # procentul folosit pentru luna asta
    gap: Decimal                        # curr - target (+ = overachievement)
    achievement_pct: Decimal | None = None  # curr / target * 100


class TgtTotals(APISchema):
    prev_sales: Decimal
    curr_sales: Decimal
    target: Decimal
    gap: Decimal
    achievement_pct: Decimal | None = None


class TgtAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str
    months: list[TgtMonthCell] = Field(default_factory=list)  # 12 items
    totals: TgtTotals


class TgtMonthTotal(APISchema):
    """Totaluri pe o lună peste toți agenții."""
    month: int
    month_name: str
    prev_sales: Decimal
    curr_sales: Decimal
    target: Decimal
    target_pct: Decimal
    gap: Decimal
    achievement_pct: Decimal | None = None


class TgtResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    agents: list[TgtAgentRow] = Field(default_factory=list)
    month_totals: list[TgtMonthTotal] = Field(default_factory=list)
    grand_totals: TgtTotals
    growth_pct: list["TgtGrowthItem"] = Field(default_factory=list)


class TgtGrowthItem(APISchema):
    year: int
    month: int
    pct: Decimal


class TgtGrowthList(APISchema):
    year: int
    items: list[TgtGrowthItem] = Field(default_factory=list)


class TgtGrowthUpsert(APISchema):
    year: int
    items: list[TgtGrowthItem] = Field(default_factory=list)
