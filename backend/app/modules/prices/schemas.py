from decimal import Decimal
from uuid import UUID

from app.core.schemas import APISchema


class PriceComparisonRow(APISchema):
    product_id: UUID | None
    description: str
    product_code: str | None
    category: str | None
    ka_price: Decimal | None
    ka_qty: Decimal
    ka_sales: Decimal
    tt_price: Decimal | None
    tt_qty: Decimal
    tt_sales: Decimal
    delta_abs: Decimal | None
    delta_pct: Decimal | None
    is_private_label: bool = False


class PriceComparisonSummary(APISchema):
    ka_avg_price: Decimal | None
    tt_avg_price: Decimal | None
    delta_pct: Decimal | None
    ka_total_sales: Decimal
    tt_total_sales: Decimal


class PriceComparisonResponse(APISchema):
    summary: PriceComparisonSummary
    rows: list[PriceComparisonRow]


# ── /prices/own — cross-KA pentru brand propriu ────────────────────────────


class CrossKaPrice(APISchema):
    price: Decimal | None
    qty: Decimal
    sales: Decimal


class CrossKaRow(APISchema):
    description: str
    product_code: str | None
    category: str | None
    prices: dict[str, CrossKaPrice]
    min_price: Decimal | None
    max_price: Decimal | None
    spread_pct: Decimal | None
    n_stores: int


class CrossKaResponse(APISchema):
    ka_clients: list[str]
    rows: list[CrossKaRow]


# ── /prices/pret3net — preț mediu per KA + discount client-side ────────────


class Pret3NetClient(APISchema):
    sales: Decimal
    qty: Decimal
    price: Decimal | None


class Pret3NetProduct(APISchema):
    description: str
    clients: dict[str, Pret3NetClient]
    total_sales: Decimal
    total_qty: Decimal
    is_private_label: bool = False


class Pret3NetResponse(APISchema):
    year: int | None
    ka_clients: list[str]
    categories: dict[str, list[Pret3NetProduct]]


# ── /prices/propuneri — produse nelistate la un KA ─────────────────────────


class PropunereRow(APISchema):
    category: str
    description: str
    total_sales: Decimal
    total_qty: Decimal
    min_price: Decimal
    min_price_ka: str
    prices: dict[str, Decimal]
    num_kas: int


class PropuneriResponse(APISchema):
    year: int | None
    ka_clients: list[str]
    suggestions: dict[str, list[PropunereRow]]


# ── /prices/ka-retail — top produse KA vs Retail ───────────────────────────


class KaRetailRow(APISchema):
    description: str
    product_code: str | None
    category: str | None
    ka_sales: Decimal
    ka_qty: Decimal
    ka_price: Decimal | None
    retail_sales: Decimal
    retail_qty: Decimal
    retail_price: Decimal | None
    diff_pct: Decimal | None
    total_sales: Decimal
    is_private_label: bool = False


class KaRetailResponse(APISchema):
    rows: list[KaRetailRow]
