from decimal import Decimal

from pydantic import Field

from app.core.schemas import APISchema


class MLGroupRow(APISchema):
    label: str
    kind: str
    key: str
    revenue: Decimal
    quantity: Decimal
    cost_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    discount_allocated: Decimal
    profit_net: Decimal
    margin_pct_net: Decimal


class MLMonthRow(APISchema):
    year: int
    month: int
    revenue_period: Decimal
    revenue_covered: Decimal
    cost_total: Decimal
    profit_total: Decimal
    margin_pct: Decimal
    discount_total: Decimal
    discount_allocated_total: Decimal
    profit_net_total: Decimal
    margin_pct_net: Decimal
    has_monthly_snapshot: bool
    fallback_revenue_pct: Decimal
    products_with_cost: int
    products_missing_cost: int
    groups: list[MLGroupRow] = Field(default_factory=list)


class MarjaLunaraResponse(APISchema):
    scope: str
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    months: list[MLMonthRow] = Field(default_factory=list)
