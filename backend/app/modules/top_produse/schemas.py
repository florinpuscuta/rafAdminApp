from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class TopProduseMonthCell(APISchema):
    month: int                          # 1..12
    month_name: str
    sales_y1: Decimal
    sales_y2: Decimal


class TopProduseProductRow(APISchema):
    rank: int                           # poziția în top (1-indexed)
    product_id: UUID
    product_code: str
    product_name: str
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None
    price_y1: Decimal | None = None
    price_y2: Decimal | None = None
    # 12 celule lunare (Ian..Dec) — populat pentru toate produsele din top.
    monthly: list[TopProduseMonthCell] = Field(default_factory=list)


class TopProduseTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class TopProduseCategoryInfo(APISchema):
    id: UUID
    code: str
    label: str


class TopProduseResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    group: str
    group_label: str
    limit: int
    last_update: datetime | None = None
    products: list[TopProduseProductRow] = Field(default_factory=list)
    totals: TopProduseTotals            # totaluri doar pe produsele din top
    available_categories: list[TopProduseCategoryInfo] = Field(default_factory=list)
    ytd_months: list[int] = Field(default_factory=list)
