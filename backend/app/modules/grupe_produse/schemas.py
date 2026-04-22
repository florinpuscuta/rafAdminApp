from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class GrupeProdusePriceCell(APISchema):
    """Preț mediu pe unitate — None când qty = 0."""
    price_y1: Decimal | None = None
    price_y2: Decimal | None = None


class GrupeProduseProductRow(APISchema):
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


class GrupeProduseTotals(APISchema):
    sales_y1: Decimal
    sales_y2: Decimal
    qty_y1: Decimal
    qty_y2: Decimal
    diff: Decimal
    pct: Decimal | None = None


class GrupeProduseCategoryInfo(APISchema):
    """Meta despre categoria curentă + lista tuturor categoriilor (pentru
    selectorul din UI)."""
    id: UUID
    code: str
    label: str


class GrupeProduseResponse(APISchema):
    scope: str                          # "adp" | "sika" | "sikadp"
    year_curr: int
    year_prev: int
    group: str                          # codul categoriei, ex "EPS"
    group_label: str                    # "Polistiren Expandat"
    last_update: datetime | None = None
    products: list[GrupeProduseProductRow] = Field(default_factory=list)
    totals: GrupeProduseTotals
    available_categories: list[GrupeProduseCategoryInfo] = Field(default_factory=list)


# ── Tree view ────────────────────────────────────────────────────────────


class TreeProductRow(APISchema):
    product_id: UUID
    code: str
    name: str
    sales: Decimal
    qty: Decimal
    sales_prev: Decimal = Decimal(0)
    qty_prev: Decimal = Decimal(0)
    avg_price: Decimal | None = None
    avg_price_prev: Decimal | None = None


class TreeSubgroup(APISchema):
    """Subgrupă în interiorul unei categorii (ex. EPS 50, EPS 80) —
    extrasă din numele produsului. Populată doar pentru anumite categorii
    (actual: EPS)."""
    key: str
    label: str
    sales: Decimal
    qty: Decimal
    sales_prev: Decimal = Decimal(0)
    qty_prev: Decimal = Decimal(0)
    products: list[TreeProductRow] = Field(default_factory=list)


class TreeCategory(APISchema):
    category_id: UUID | None = None
    code: str
    label: str
    sales: Decimal
    qty: Decimal
    sales_prev: Decimal = Decimal(0)
    qty_prev: Decimal = Decimal(0)
    products: list[TreeProductRow] = Field(default_factory=list)
    subgroups: list[TreeSubgroup] | None = None


class TreeBrand(APISchema):
    brand_id: UUID | None = None
    name: str
    is_private_label: bool
    sales: Decimal
    qty: Decimal
    sales_prev: Decimal = Decimal(0)
    qty_prev: Decimal = Decimal(0)
    categories: list[TreeCategory] = Field(default_factory=list)


class GrupeProduseTreeResponse(APISchema):
    scope: str
    year: int
    last_update: datetime | None = None
    brands: list[TreeBrand] = Field(default_factory=list)
    grand_sales: Decimal
    grand_qty: Decimal
    grand_sales_prev: Decimal = Decimal(0)
    grand_qty_prev: Decimal = Decimal(0)
    ytd_months: list[int] = Field(default_factory=list)
    selected_months: list[int] = Field(default_factory=list)
