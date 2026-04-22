"""
"Mortare Silozuri (Vrac)" — vânzări mortare vrac, breakdown lunar y vs y-1.

Filtrul canonic (spre deosebire de legacy care aplica LIKE pe description):
    raw_sales → products.category_id → product_categories WHERE code = 'VARSACI'

Doar rândurile cu product_id rezolvat la un Product care are category_id pe
categoria VARSACI (global). Rândurile cu product_id NULL sau categorie diferită
NU intră.

Output per lună: (qty_y1, qty_y2, sales_y1, sales_y2, diff, pct).
Plus listă produse cu totaluri pe ambii ani.

Surse per scope:
  - adp → [["sales_xlsx"]]

(Sika nu produce mortare vrac — feature-ul e doar pe Adeplast.)

Rezolvare SAM o aplicăm pentru coerență cu restul modulelor, deși nu o
folosim la agregare la nivel de agent (agregăm pe produs + lună).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale


def _silozuri_filter():
    """Filtrează doar mortarele de siloz Adeplast listate explicit:
    - MORTAR MTI 25 VRAC
    - MORTAR MTE 35 VRAC
    - mortar glet MTIG VRAC
    - MZ 50 VRAC / MZC 5 VRAC (variante mortar zidărie)

    Holcim cimenturile vrac + celelalte produse NU intră aici.
    """
    return or_(
        Product.name.ilike("%MTI 25%VRAC%"),
        Product.name.ilike("%MTE 35%VRAC%"),
        Product.name.ilike("%MTIG%VRAC%"),
        Product.name.ilike("%MZ 50%VRAC%"),
        Product.name.ilike("%MZC 5%VRAC%"),
    )


_MONTH_NAMES = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


def month_name(m: int) -> str:
    return _MONTH_NAMES[m] if 1 <= m <= 12 else ""


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]

# Vezi `_silozuri_filter()` — filtrul pentru produsele de tip mortar/ciment
# vrac. NU mai folosim categoria VARSACI (acolo e "Var si Aci", nu silozuri).


@dataclass
class MonthCell:
    month: int
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)
    qty_y1: Decimal = Decimal(0)
    qty_y2: Decimal = Decimal(0)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)


@dataclass
class ProductRow:
    product_id: UUID | None
    product_code: str | None
    product_name: str
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)
    qty_y1: Decimal = Decimal(0)
    qty_y2: Decimal = Decimal(0)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)


@dataclass
class MortareData:
    scope: str
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    months: dict[int, MonthCell] = field(default_factory=dict)
    products: list[ProductRow] = field(default_factory=list)

    def cell(self, m: int) -> MonthCell:
        return self.months.setdefault(m, MonthCell(month=m))


# ── Internal helpers ─────────────────────────────────────────────────────


async def _months_with_data(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int,
    batch_source_groups: list[list[str]],
) -> set[int]:
    sources = {s for g in batch_source_groups for s in g}
    if not sources:
        return set()
    stmt = (
        select(RawSale.month)
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year == year,
            _silozuri_filter(),
            ImportBatch.source.in_(sources),
        )
        .distinct()
    )
    return {int(r.month) for r in (await session.execute(stmt)).all()}


async def _monthly_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None,
) -> list[dict[str, Any]]:
    year_prev = year_curr - 1
    out: dict[tuple[int, int], dict[str, Any]] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(Product, Product.id == RawSale.product_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    _silozuri_filter(),
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            }
            if months_filter is not None:
                source_pairs = {(y, m) for (y, m) in source_pairs if m in months_filter}
            new_pairs = source_pairs - claimed_pairs
            if not new_pairs:
                continue

            new_years = {y for (y, _m) in new_pairs}
            new_months = {m for (_y, m) in new_pairs}
            stmt = (
                select(
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                    func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
                )
                .join(Product, Product.id == RawSale.product_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    _silozuri_filter(),
                    ImportBatch.source == src,
                )
                .group_by(RawSale.year, RawSale.month)
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs:
                    continue
                key = ym
                row = out.setdefault(key, {
                    "year": int(r.year),
                    "month": int(r.month),
                    "amount": Decimal(0),
                    "quantity": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)
                row["quantity"] += Decimal(r.qty or 0)

            claimed_pairs |= new_pairs

    return list(out.values())


async def _product_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None,
) -> list[dict[str, Any]]:
    """Agregare pe (product_id, year) pentru listă produse."""
    year_prev = year_curr - 1
    sources = {s for g in batch_source_groups for s in g}
    if not sources:
        return []

    filters = [
        RawSale.tenant_id == tenant_id,
        RawSale.year.in_([year_prev, year_curr]),
        _silozuri_filter(),
        ImportBatch.source.in_(sources),
    ]
    if months_filter is not None and months_filter:
        filters.append(RawSale.month.in_(list(months_filter)))

    stmt = (
        select(
            Product.id.label("product_id"),
            Product.code.label("product_code"),
            Product.name.label("product_name"),
            RawSale.year,
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(*filters)
        .group_by(Product.id, Product.code, Product.name, RawSale.year)
    )
    result = await session.execute(stmt)
    return [
        {
            "product_id": r.product_id,
            "product_code": r.product_code,
            "product_name": r.product_name,
            "year": int(r.year),
            "amount": Decimal(r.amt or 0),
            "quantity": Decimal(r.qty or 0),
        }
        for r in result.all()
    ]


async def _last_update(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    sources: list[str],
) -> datetime | None:
    stmt = select(func.max(ImportBatch.created_at)).where(
        ImportBatch.tenant_id == tenant_id,
        ImportBatch.source.in_(sources),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# ── Public entry-points ──────────────────────────────────────────────────


async def _build(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None = None,
) -> MortareData:
    if months_filter is None:
        months_filter = await _months_with_data(
            session, tenant_id,
            year=year_curr, batch_source_groups=batch_source_groups,
        )

    year_prev = year_curr - 1
    data = MortareData(
        scope=scope,
        year_curr=year_curr,
        year_prev=year_prev,
    )

    # 1) Agregare lunară
    monthly = await _monthly_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        months_filter=months_filter,
    )
    for r in monthly:
        cell = data.cell(r["month"])
        if r["year"] == year_prev:
            cell.sales_y1 += r["amount"]
            cell.qty_y1 += r["quantity"]
        elif r["year"] == year_curr:
            cell.sales_y2 += r["amount"]
            cell.qty_y2 += r["quantity"]

    # 2) Completare 12 luni
    for m in range(1, 13):
        data.cell(m)

    # 3) Agregare pe produs
    prod_rows = await _product_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        months_filter=months_filter,
    )
    by_product: dict[UUID, ProductRow] = {}
    for r in prod_rows:
        pid: UUID = r["product_id"]
        pr = by_product.setdefault(pid, ProductRow(
            product_id=pid,
            product_code=r["product_code"],
            product_name=r["product_name"] or (r["product_code"] or "—"),
        ))
        if r["year"] == year_prev:
            pr.sales_y1 += r["amount"]
            pr.qty_y1 += r["quantity"]
        elif r["year"] == year_curr:
            pr.sales_y2 += r["amount"]
            pr.qty_y2 += r["quantity"]

    data.products = sorted(
        by_product.values(),
        key=lambda p: (-(p.sales_y1 or Decimal(0)), -(p.sales_y2 or Decimal(0))),
    )

    data.last_update = await _last_update(
        session, tenant_id,
        sources=[s for g in batch_source_groups for s in g],
    )
    return data


async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    months_filter: set[int] | None = None,
) -> MortareData:
    return await _build(
        session, tenant_id,
        scope="adp", year_curr=year_curr,
        batch_source_groups=_GROUPS_ADP,
        months_filter=months_filter,
    )
