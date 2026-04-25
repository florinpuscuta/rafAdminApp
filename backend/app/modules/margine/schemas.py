from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class MargineProductRow(APISchema):
    product_id: UUID
    product_code: str
    product_name: str
    revenue: Decimal
    quantity: Decimal
    avg_sale: Decimal
    cost: Decimal
    profit: Decimal
    margin_pct: Decimal


class MargineGroupRow(APISchema):
    label: str
    kind: str  # "category" | "tm" | "private_label"
    key: str
    revenue: Decimal
    quantity: Decimal
    cost_total: Decimal
    profit: Decimal
    margin_pct: Decimal
    discount_allocated: Decimal
    profit_net: Decimal
    margin_pct_net: Decimal
    products: list[MargineProductRow] = Field(default_factory=list)


class MargineMissingRow(APISchema):
    product_id: UUID
    product_code: str
    product_name: str
    revenue: Decimal
    quantity: Decimal


class MargineResponse(APISchema):
    scope: str
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    revenue_period: Decimal
    revenue_covered: Decimal
    cost_total: Decimal
    profit_total: Decimal
    margin_pct: Decimal
    coverage_pct: Decimal
    discount_total: Decimal
    discount_allocated_total: Decimal
    profit_net_total: Decimal
    margin_pct_net: Decimal
    products_with_cost: int
    products_missing_cost: int
    groups: list[MargineGroupRow] = Field(default_factory=list)
    missing_cost: list[MargineMissingRow] = Field(default_factory=list)
