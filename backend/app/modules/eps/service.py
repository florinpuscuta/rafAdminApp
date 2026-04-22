"""
Agregări pentru EPS (Polistiren Expandat).

Query-ul folosește calea canonică:
    raw_sales → products → product_categories WHERE code = 'EPS'

Asta înseamnă: doar vânzările unde `raw_sales.product_id` a fost rezolvat
la un Product care are `category_id` pe categoria EPS (global). Rândurile
nemapate (product_id NULL) NU intră — sunt "unmapped" și vizibile separat
în UI-ul de mapping.

Clasificare canal: UPPER(raw_sales.channel) = 'KA' → 'KA', else 'RETAIL'.
(Channel-ul rămâne string pe raw_sales — are 2-4 valori fixe, nu merită
tabel separat.)
"""
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import RawSale


_MONTH_NAMES = [
    "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
]


async def details_by_month(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    y1: int,
    y2: int,
    months: Iterable[int] | None = None,
) -> list[dict]:
    """
    Returnează [{category, month, month_name, qty_y1, qty_y2, sales_y1,
    sales_y2}, ...] grupat pe (canal KA/RETAIL, lună).
    """
    channel_cat = case(
        (func.upper(RawSale.channel) == "KA", "KA"),
        else_="RETAIL",
    ).label("category")

    filters = [
        RawSale.tenant_id == tenant_id,
        RawSale.year.in_([y1, y2]),
        ProductCategory.code == "EPS",
        # Doar KA (perle/granule/blocuri/deșeuri EPS — "non-MM" — excluse;
        # retail canal exclus: pagina arată total EPS plăci pe KA).
        func.upper(RawSale.channel) == "KA",
        Product.name.op("~*")(r"\d+\s*MM"),
    ]
    months_list = list(months) if months is not None else None
    if months_list:
        filters.append(RawSale.month.in_(months_list))

    qty_y1 = func.coalesce(
        func.sum(case((RawSale.year == y1, RawSale.quantity), else_=0)), 0
    )
    qty_y2 = func.coalesce(
        func.sum(case((RawSale.year == y2, RawSale.quantity), else_=0)), 0
    )
    sales_y1 = func.coalesce(
        func.sum(case((RawSale.year == y1, RawSale.amount), else_=0)), 0
    )
    sales_y2 = func.coalesce(
        func.sum(case((RawSale.year == y2, RawSale.amount), else_=0)), 0
    )

    stmt = (
        select(
            channel_cat,
            RawSale.month.cast(Integer).label("month"),
            qty_y1.label("qty_y1"),
            qty_y2.label("qty_y2"),
            sales_y1.label("sales_y1"),
            sales_y2.label("sales_y2"),
        )
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(*filters)
        .group_by(channel_cat, RawSale.month)
        .order_by(channel_cat, RawSale.month)
    )
    result = await session.execute(stmt)
    return [
        {
            "category": row.category,
            "month": int(row.month),
            "month_name": _MONTH_NAMES[int(row.month)] if 1 <= int(row.month) <= 12 else str(row.month),
            "qty_y1": Decimal(row.qty_y1 or 0),
            "qty_y2": Decimal(row.qty_y2 or 0),
            "sales_y1": Decimal(row.sales_y1 or 0),
            "sales_y2": Decimal(row.sales_y2 or 0),
        }
        for row in result.all()
    ]


async def breakdown_by_class(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    y1: int,
    y2: int,
    months: Iterable[int] | None = None,
) -> list[dict]:
    """Breakdown pe clasa EPS (50/70/80/100/120/150/200), KA only, plăci
    (cu MM în nume). Scoate primul număr după 'EPS' din numele produsului.
    """
    from sqlalchemy import text

    # Extragem clasa: primul număr după "EPS" (ex. "ADEPLAST EPS 80+ 100MM" → "80").
    class_col = func.substring(Product.name, r"[Ee][Pp][Ss][ _-]*(\d+)").label("cls")

    filters = [
        RawSale.tenant_id == tenant_id,
        RawSale.year.in_([y1, y2]),
        ProductCategory.code == "EPS",
        func.upper(RawSale.channel) == "KA",
        Product.name.op("~*")(r"\d+\s*MM"),
    ]
    months_list = list(months) if months is not None else None
    if months_list:
        filters.append(RawSale.month.in_(months_list))

    qty_y1 = func.coalesce(
        func.sum(case((RawSale.year == y1, RawSale.quantity), else_=0)), 0
    )
    qty_y2 = func.coalesce(
        func.sum(case((RawSale.year == y2, RawSale.quantity), else_=0)), 0
    )
    sales_y1 = func.coalesce(
        func.sum(case((RawSale.year == y1, RawSale.amount), else_=0)), 0
    )
    sales_y2 = func.coalesce(
        func.sum(case((RawSale.year == y2, RawSale.amount), else_=0)), 0
    )

    stmt = (
        select(
            class_col,
            qty_y1.label("qty_y1"),
            qty_y2.label("qty_y2"),
            sales_y1.label("sales_y1"),
            sales_y2.label("sales_y2"),
        )
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(*filters)
        .group_by(class_col)
        .order_by(class_col)
    )
    result = await session.execute(stmt)
    return [
        {
            "cls": str(row.cls or "UNK"),
            "qty_y1": Decimal(row.qty_y1 or 0),
            "qty_y2": Decimal(row.qty_y2 or 0),
            "sales_y1": Decimal(row.sales_y1 or 0),
            "sales_y2": Decimal(row.sales_y2 or 0),
        }
        for row in result.all()
    ]
