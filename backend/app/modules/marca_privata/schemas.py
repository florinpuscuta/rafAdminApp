from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.core.schemas import APISchema


class MPYearTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MPMonthCell(APISchema):
    month: int
    month_name: str
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MPClientRow(APISchema):
    client: str
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MPResponse(APISchema):
    scope: str                          # "adp"
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    months: list[MPMonthCell] = Field(default_factory=list)   # 12 items
    clients: list[MPClientRow] = Field(default_factory=list)
    grand_totals: MPYearTotals
