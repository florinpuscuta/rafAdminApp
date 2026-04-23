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


class MPCategoryCell(APISchema):
    code: str            # "MU" | "EPS" | "UMEDE"
    label: str           # "Mortare Uscate" | "EPS" | "Umede"
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class MPChainRow(APISchema):
    chain: str           # "Dedeman" | "Altex" | "Leroy Merlin" | "Hornbach" | "Alte"
    sales_y1: Decimal
    sales_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None
    categories: list[MPCategoryCell] = Field(default_factory=list)


class MPResponse(APISchema):
    scope: str                          # "adp"
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    months: list[MPMonthCell] = Field(default_factory=list)   # 12 items
    chains: list[MPChainRow] = Field(default_factory=list)
    grand_totals: MPYearTotals
