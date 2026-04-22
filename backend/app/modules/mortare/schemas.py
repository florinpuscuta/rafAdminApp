from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class MortareYearTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MortareMonthCell(APISchema):
    month: int
    month_name: str
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MortareProductRow(APISchema):
    product_id: UUID | None
    product_code: str | None
    product_name: str
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MortareResponse(APISchema):
    scope: str                        # "adp"
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    months: list[MortareMonthCell] = Field(default_factory=list)       # 12 items
    products: list[MortareProductRow] = Field(default_factory=list)
    grand_totals: MortareYearTotals
