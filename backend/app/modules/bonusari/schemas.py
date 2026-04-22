from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class BonTier(APISchema):
    threshold_pct: Decimal
    amount: Decimal


class BonRules(APISchema):
    tiers: list[BonTier] = Field(default_factory=list)
    recovery_amount: Decimal
    recovery_threshold_pct: Decimal


class BonMonthCell(APISchema):
    month: int                          # 1..12
    month_name: str
    prev_sales: Decimal
    curr_sales: Decimal
    growth_pct: Decimal
    bonus: Decimal
    recovery: Decimal
    total: Decimal
    is_future: bool


class BonAgentRow(APISchema):
    agent_id: UUID | None
    agent_name: str
    months: list[BonMonthCell] = Field(default_factory=list)  # 12 items
    total_bonus: Decimal


class BonMonthTotal(APISchema):
    """Totaluri per lună peste toți agenții."""
    month: int
    month_name: str
    bonus: Decimal
    recovery: Decimal
    total: Decimal


class BonResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    current_month_limit: int            # ultima lună eligibilă (current/param)
    rules: BonRules
    last_update: datetime | None = None
    agents: list[BonAgentRow] = Field(default_factory=list)
    month_totals: list[BonMonthTotal] = Field(default_factory=list)
    grand_total: Decimal
