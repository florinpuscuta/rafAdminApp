"""
"Top Produse" — top-N produse KA dintr-o categorie, sortat după vânzările Y2.

Pentru fiecare produs (cu `product_id` rezolvat și `category_id` = grupul cerut):
  - sales_y1 / qty_y1 / price_y1 (Y1 = year-1)
  - sales_y2 / qty_y2 / price_y2 (Y2 = year)
  - diff / pct

Plus breakdown lunar (Ian..Dec) pentru top 5 produse — folosit la trend chart.

Surse per scope — identic cu `grupe_produse`:
  - adp    → [["sales_xlsx"]]
  - sika   → [["sika_mtd_xlsx", "sika_xlsx"]]
  - sikadp → [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale


_MONTH_NAMES = [
    "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
    "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
]


def month_name(m: int) -> str:
    return _MONTH_NAMES[m] if 1 <= m <= 12 else ""


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]
_GROUPS_SIKADP: list[list[str]] = [
    ["sales_xlsx"],
    ["sika_mtd_xlsx", "sika_xlsx"],
]


@dataclass
class TopProductMonth:
    month: int
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)


@dataclass
class TopProductRow:
    product_id: UUID
    product_code: str
    product_name: str
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)
    qty_y1: Decimal = Decimal(0)
    qty_y2: Decimal = Decimal(0)
    monthly: dict[int, TopProductMonth] = field(default_factory=dict)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)

    @property
    def price_y1(self) -> Decimal | None:
        if self.qty_y1 == 0:
            return None
        return self.sales_y1 / self.qty_y1

    @property
    def price_y2(self) -> Decimal | None:
        if self.qty_y2 == 0:
            return None
        return self.sales_y2 / self.qty_y2


async def _category_id_by_code(
    session: AsyncSession, code: str,
) -> tuple[UUID, str] | None:
    row = (await session.execute(
        select(ProductCategory.id, ProductCategory.label)
        .where(ProductCategory.code == code.upper())
    )).first()
    if row is None:
        return None
    return row[0], row[1]


async def _monthly_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    category_id: UUID,
    batch_source_groups: list[list[str]],
) -> list[dict[str, Any]]:
    """Rânduri agregate pe (product_id, year, month). Aplică dedup SIKA la
    nivel de (year, month) în interiorul grupului, apoi însumează grupurile.
    """
    year_prev = year_curr - 1
    out: dict[tuple[UUID, int, int], dict[str, Any]] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            }
            new_pairs = source_pairs - claimed_pairs
            if not new_pairs:
                continue

            new_years = {y for (y, _m) in new_pairs}
            new_months = {m for (_y, m) in new_pairs}

            stmt = (
                select(
                    RawSale.product_id,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                    func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .join(Product, Product.id == RawSale.product_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                    Product.category_id == category_id,
                )
                .group_by(RawSale.product_id, RawSale.year, RawSale.month)
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs or r.product_id is None:
                    continue
                key = (r.product_id, int(r.year), int(r.month))
                row = out.setdefault(key, {
                    "product_id": r.product_id,
                    "year": int(r.year),
                    "month": int(r.month),
                    "amount": Decimal(0),
                    "quantity": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)
                row["quantity"] += Decimal(r.qty or 0)

            claimed_pairs |= new_pairs

    return list(out.values())


async def _hydrate_products(
    session: AsyncSession,
    tenant_id: UUID,
    product_ids: set[UUID],
) -> dict[UUID, tuple[str, str]]:
    if not product_ids:
        return {}
    rows = (await session.execute(
        select(Product.id, Product.code, Product.name)
        .where(Product.tenant_id == tenant_id, Product.id.in_(product_ids))
    )).all()
    return {r[0]: (r[1], r[2]) for r in rows}


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


async def _build_top(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    category_id: UUID,
    batch_source_groups: list[list[str]],
    limit: int,
) -> tuple[list[TopProductRow], list[int]]:
    year_prev = year_curr - 1

    rows = await _monthly_rows(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=batch_source_groups,
    )

    # YTD auto: lunile cu date în anul curent → perioada de comparație
    # (anul precedent e restrâns la aceleași luni).
    ytd_months = sorted({r["month"] for r in rows if r["year"] == year_curr})
    ytd_set = set(ytd_months)

    by_product: dict[UUID, TopProductRow] = {}
    for r in rows:
        pid = r["product_id"]
        y = r["year"]
        m = r["month"]
        # Filtrăm an precedent la aceleași luni ca YTD curent.
        if y == year_prev and m not in ytd_set:
            continue
        if y == year_curr and m not in ytd_set:
            continue
        pr = by_product.setdefault(
            pid,
            TopProductRow(product_id=pid, product_code="", product_name=""),
        )
        amt = r["amount"]
        qty = r["quantity"]
        if y == year_prev:
            pr.sales_y1 += amt
            pr.qty_y1 += qty
        elif y == year_curr:
            pr.sales_y2 += amt
            pr.qty_y2 += qty
        cell = pr.monthly.setdefault(m, TopProductMonth(month=m))
        if y == year_prev:
            cell.sales_y1 += amt
        elif y == year_curr:
            cell.sales_y2 += amt

    meta = await _hydrate_products(session, tenant_id, set(by_product.keys()))
    for pid, pr in by_product.items():
        code, name = meta.get(pid, ("", ""))
        pr.product_code = code or ""
        pr.product_name = name or ""

    def _sort_key(p: TopProductRow) -> tuple[Decimal, Decimal, str]:
        return (-p.sales_y2, -p.sales_y1, p.product_name.lower())

    ordered = sorted(by_product.values(), key=_sort_key)
    return ordered[: max(1, limit)], ytd_months


# ── Public entry-points ──────────────────────────────────────────────────


async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID, limit: int,
) -> dict[str, Any]:
    products, ytd_months = await _build_top(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_ADP, limit=limit,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_ADP for s in g],
    )
    return {
        "scope": "adp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "products": products,
        "ytd_months": ytd_months,
    }


async def get_for_sika(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID, limit: int,
) -> dict[str, Any]:
    products, ytd_months = await _build_top(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_SIKA, limit=limit,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKA for s in g],
    )
    return {
        "scope": "sika",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "products": products,
        "ytd_months": ytd_months,
    }


async def get_for_sikadp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID, limit: int,
) -> dict[str, Any]:
    products, ytd_months = await _build_top(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_SIKADP, limit=limit,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKADP for s in g],
    )
    return {
        "scope": "sikadp",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "products": products,
        "ytd_months": ytd_months,
    }


async def list_categories(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.execute(
        select(ProductCategory.id, ProductCategory.code, ProductCategory.label,
               ProductCategory.sort_order)
        .order_by(ProductCategory.sort_order, ProductCategory.code)
    )).all()
    return [
        {"id": r[0], "code": r[1], "label": r[2], "sort_order": r[3]}
        for r in rows
    ]


async def resolve_category(
    session: AsyncSession, code: str,
) -> tuple[UUID, str] | None:
    return await _category_id_by_code(session, code)


# ── Sika Target Markets (scope=sika) ─────────────────────────────────────
# Cod TM → (label, regex). Produsele Sika sunt clasificate după nume.
# Sursa regexurilor: `grupe_produse.service._SIKA_TM_RULES` (sincronizat).


TM_CODES: dict[str, str] = {
    "TM-BF": "Building Finishing",
    "TM-SB": "Sealing & Bonding",
    "TM-WP": "Waterproofing & Roofing",
    "TM-CA": "Concrete & Anchors",
    "TM-IA": "Industry & Accessories",
    "TM-FL": "Flooring",
}


def is_tm_code(code: str) -> bool:
    return code.upper() in TM_CODES


def resolve_tm(code: str) -> tuple[str, str] | None:
    """Returnează (code_upper, label) pentru un cod TM validat."""
    up = code.upper()
    if up not in TM_CODES:
        return None
    return up, TM_CODES[up]


async def _products_for_sika_tm(
    session: AsyncSession,
    tenant_id: UUID,
    tm_label: str,
) -> set[UUID]:
    """ID-urile produselor Sika care cad în TM-ul dat (match pe nume)."""
    from app.modules.brands.models import Brand
    from app.modules.grupe_produse.service import classify_sika_tm

    rows = (await session.execute(
        select(Product.id, Product.name)
        .join(Brand, Brand.id == Product.brand_id)
        .where(
            Product.tenant_id == tenant_id,
            Brand.name == "Sika",
        )
    )).all()
    return {r.id for r in rows if classify_sika_tm(r.name) == tm_label}


async def _monthly_rows_by_ids(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    product_ids: set[UUID],
    batch_source_groups: list[list[str]],
) -> list[dict[str, Any]]:
    """Varianta `_monthly_rows` dar filtrată pe o listă concretă de product_ids
    (folosită pentru TM-urile Sika, unde nu există `category_id` stabil)."""
    year_prev = year_curr - 1
    if not product_ids:
        return []
    out: dict[tuple[UUID, int, int], dict[str, Any]] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            }
            new_pairs = source_pairs - claimed_pairs
            if not new_pairs:
                continue
            new_years = {y for (y, _m) in new_pairs}
            new_months = {m for (_y, m) in new_pairs}

            stmt = (
                select(
                    RawSale.product_id,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                    func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                    RawSale.product_id.in_(product_ids),
                )
                .group_by(RawSale.product_id, RawSale.year, RawSale.month)
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs or r.product_id is None:
                    continue
                key = (r.product_id, int(r.year), int(r.month))
                row = out.setdefault(key, {
                    "product_id": r.product_id,
                    "year": int(r.year),
                    "month": int(r.month),
                    "amount": Decimal(0),
                    "quantity": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)
                row["quantity"] += Decimal(r.qty or 0)
            claimed_pairs |= new_pairs

    return list(out.values())


async def _build_top_by_ids(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    product_ids: set[UUID],
    batch_source_groups: list[list[str]],
    limit: int,
) -> tuple[list[TopProductRow], list[int]]:
    """Variantă _build_top cu filtrare pe IDs (pentru TM Sika)."""
    year_prev = year_curr - 1
    rows = await _monthly_rows_by_ids(
        session, tenant_id,
        year_curr=year_curr, product_ids=product_ids,
        batch_source_groups=batch_source_groups,
    )
    ytd_months = sorted({r["month"] for r in rows if r["year"] == year_curr})
    ytd_set = set(ytd_months)

    by_product: dict[UUID, TopProductRow] = {}
    for r in rows:
        pid = r["product_id"]
        y = r["year"]
        m = r["month"]
        if m not in ytd_set:
            continue
        pr = by_product.setdefault(
            pid,
            TopProductRow(product_id=pid, product_code="", product_name=""),
        )
        amt = r["amount"]
        qty = r["quantity"]
        if y == year_prev:
            pr.sales_y1 += amt
            pr.qty_y1 += qty
        elif y == year_curr:
            pr.sales_y2 += amt
            pr.qty_y2 += qty
        cell = pr.monthly.setdefault(m, TopProductMonth(month=m))
        if y == year_prev:
            cell.sales_y1 += amt
        elif y == year_curr:
            cell.sales_y2 += amt

    meta = await _hydrate_products(session, tenant_id, set(by_product.keys()))
    for pid, pr in by_product.items():
        code, name = meta.get(pid, ("", ""))
        pr.product_code = code or ""
        pr.product_name = name or ""

    ordered = sorted(
        by_product.values(),
        key=lambda p: (-p.sales_y2, -p.sales_y1, p.product_name.lower()),
    )
    return ordered[: max(1, limit)], ytd_months


async def get_for_sika_tm(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, tm_label: str, limit: int,
) -> dict[str, Any]:
    """Top produse Sika pentru un Target Market specific."""
    product_ids = await _products_for_sika_tm(session, tenant_id, tm_label)
    products, ytd_months = await _build_top_by_ids(
        session, tenant_id,
        year_curr=year_curr, product_ids=product_ids,
        batch_source_groups=_GROUPS_SIKA, limit=limit,
    )
    last_update = await _last_update(
        session, tenant_id, sources=[s for g in _GROUPS_SIKA for s in g],
    )
    return {
        "scope": "sika",
        "year_curr": year_curr,
        "year_prev": year_curr - 1,
        "last_update": last_update,
        "products": products,
        "ytd_months": ytd_months,
    }
