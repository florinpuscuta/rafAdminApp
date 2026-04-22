from decimal import Decimal

from app.core.schemas import APISchema


class EpsMonthlyRow(APISchema):
    category: str  # 'KA' | 'RETAIL'
    month: int  # 1..12
    month_name: str
    qty_y1: Decimal
    qty_y2: Decimal
    sales_y1: Decimal
    sales_y2: Decimal


class EpsDetailsResponse(APISchema):
    y1: int
    y2: int
    rows: list[EpsMonthlyRow]


class EpsClassRow(APISchema):
    cls: str  # ex. "50", "80", "100", "120", ...
    qty_y1: Decimal
    qty_y2: Decimal
    sales_y1: Decimal
    sales_y2: Decimal


class EpsBreakdownResponse(APISchema):
    y1: int
    y2: int
    rows: list[EpsClassRow]
