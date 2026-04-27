"""
"Analiza Magazin Dashboard" — KPI complet pentru un magazin canonic.

Pentru un magazin selectat (canonical `store_id`), construiește un dashboard cu:
  - KPI perioada curentă (ultimele N luni cu date) — vânzări, SKU, cantitate
  - YoY: aceleași luni, anul precedent (delta absolut + procent)
  - MoM: ferestră N luni precedente (delta absolut + procent)
  - Serie lunară: per lună, vânzări curent vs YoY, SKU curent vs YoY
  - Breakdown pe categorie de produs (ProductCategory.code)
  - Brand vs Marcă Privată (Brand.is_private_label)

Sursa de adevăr pentru ierarhia client→magazin: `store_agent_mappings`
(client_original = "DEDEMAN SRL" / "ALTEX ROMANIA SRL" / etc., store_id = canonic).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.period_math import shift_months, window_pairs
from app.modules.brands.models import Brand
from app.modules.mappings.models import StoreAgentMapping
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale
from app.modules.stores.models import Store


ALLOWED_MONTHS_WINDOWS: tuple[int, ...] = (3, 6, 9, 12)
DEFAULT_MONTHS_WINDOW: int = 3


# Cei 4 clienți KA — eticheta UI → `client_original` din `store_agent_mappings`.
KA_CLIENTS: dict[str, str] = {
    "Dedeman": "DEDEMAN SRL",
    "Altex": "ALTEX ROMANIA SRL",
    "Leroy Merlin": "LEROY MERLIN ROMANIA SRL",
    "Hornbach": "HORNBACH CENTRALA SRL",
}


# scope firmă → surse `ImportBatch.source` acceptate.
SCOPE_SOURCES: dict[str, list[str]] = {
    "adp": ["sales_xlsx"],
    "sika": ["sika_mtd_xlsx", "sika_xlsx"],
}


# Window arithmetic — folosim `app.core.period_math` ca sa avem o singura
# sursa de adevar pentru calculele pe luni calendaristice. Pastram alias-uri
# private pentru continuitate, dar consumatorii ar trebui sa importe public.
_shift = shift_months
_window_pairs = window_pairs


# ── Public dataclasses ───────────────────────────────────────────────────


@dataclass
class StoreOption:
    store_id: UUID
    name: str


@dataclass
class Metrics:
    sales: Decimal = Decimal(0)
    quantity: Decimal = Decimal(0)
    sku_count: int = 0


@dataclass
class MonthSeries:
    year: int
    month: int
    sales_curr: Decimal = Decimal(0)
    sales_prev_year: Decimal = Decimal(0)
    sku_curr: int = 0
    sku_prev_year: int = 0


@dataclass
class CategoryRow:
    code: str
    label: str
    curr: Metrics = field(default_factory=Metrics)
    yoy: Metrics = field(default_factory=Metrics)


@dataclass
class BrandSplit:
    brand: Metrics = field(default_factory=Metrics)
    private_label: Metrics = field(default_factory=Metrics)
    brand_yoy: Metrics = field(default_factory=Metrics)
    private_label_yoy: Metrics = field(default_factory=Metrics)


@dataclass
class ProductRow:
    product_id: UUID
    code: str
    name: str
    category_code: str | None
    category_label: str | None
    curr: Metrics = field(default_factory=Metrics)
    yoy: Metrics = field(default_factory=Metrics)


@dataclass
class DashboardData:
    scope: str
    store_id: UUID
    store_name: str
    months_window: int
    window_curr: list[tuple[int, int]]
    window_yoy: list[tuple[int, int]]
    window_prev: list[tuple[int, int]]
    kpi_curr: Metrics
    kpi_yoy: Metrics
    kpi_prev: Metrics
    monthly: list[MonthSeries]
    categories: list[CategoryRow]
    brand_split: BrandSplit
    products: list[ProductRow] = field(default_factory=list)


# ── Selectoare client / magazin ──────────────────────────────────────────


def list_clients() -> list[str]:
    """Eticheta UI a celor 4 clienți KA."""
    return list(KA_CLIENTS.keys())


async def list_stores_for_client(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    client: str,
) -> list[StoreOption]:
    """Magazinele canonice ale unui client KA, din `store_agent_mappings`."""
    if client not in KA_CLIENTS:
        return []
    client_original = KA_CLIENTS[client]

    stmt = (
        select(Store.id, Store.name)
        .join(
            StoreAgentMapping,
            StoreAgentMapping.store_id == Store.id,
        )
        .where(
            StoreAgentMapping.tenant_id == tenant_id,
            StoreAgentMapping.client_original == client_original,
            StoreAgentMapping.store_id.is_not(None),
        )
        .distinct()
        .order_by(Store.name)
    )
    rows = (await session.execute(stmt)).all()
    return [StoreOption(store_id=r.id, name=str(r.name)) for r in rows]


# ── Window discovery ─────────────────────────────────────────────────────


async def _latest_month_with_data(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    sources: list[str],
) -> tuple[int, int] | None:
    """Cel mai recent (year, month) cu date în tenant × surse (orice magazin)."""
    if not sources:
        return None
    stmt = (
        select(RawSale.year, RawSale.month)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            ImportBatch.source.in_(sources),
        )
        .order_by(RawSale.year.desc(), RawSale.month.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        return None
    return int(row.year), int(row.month)


# ── Aggregation primitives ───────────────────────────────────────────────


def _ym_set(pairs: list[tuple[int, int]]) -> tuple[set[int], set[int]]:
    """Helper: set-uri de ani/luni pentru filtre IN. Filtrează pe (year,month)
    cartezian; pentru ferestre ≤ 12 luni e ok să avem 1-2 valori extra
    apoi filtrăm post-fetch după pereche."""
    return {y for (y, _m) in pairs}, {m for (_y, m) in pairs}


def _filter_pairs(rows, pairs: list[tuple[int, int]]):
    """Păstrează doar rândurile cu (year, month) în set."""
    keep = set(pairs)
    return [r for r in rows if (int(r.year), int(r.month)) in keep]


async def _aggregate_window(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store_id: UUID,
    sources: list[str],
    pairs: list[tuple[int, int]],
) -> Metrics:
    """Sales/qty/SKU pe (store, sources, year_month-pairs)."""
    if not pairs:
        return Metrics()
    years, months = _ym_set(pairs)

    stmt = (
        select(
            RawSale.year,
            RawSale.month,
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
        )
        .group_by(RawSale.year, RawSale.month)
    )
    raw_rows = _filter_pairs((await session.execute(stmt)).all(), pairs)

    # SKU distinct: filtrăm pe pereche (year,month) post-fetch — IN+IN e
    # produs cartezian, deci avem nevoie de filtru exact pentru a nu număra
    # SKU-uri din luni vecine care nu sunt în fereastră.
    sku_pairs_stmt = (
        select(RawSale.year, RawSale.month, RawSale.product_id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .distinct()
    )
    distinct_skus = {
        r.product_id for r in (await session.execute(sku_pairs_stmt)).all()
        if (int(r.year), int(r.month)) in set(pairs)
    }

    out = Metrics(sku_count=len(distinct_skus))
    for r in raw_rows:
        out.sales += Decimal(r.amt or 0)
        out.quantity += Decimal(r.qty or 0)
    return out


async def _monthly_series(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store_id: UUID,
    sources: list[str],
    pairs_curr: list[tuple[int, int]],
    pairs_yoy: list[tuple[int, int]],
) -> list[MonthSeries]:
    """Serie lunară: pentru fiecare (year, month) din pairs_curr, calculează
    vânzări + SKU în acea lună și în luna echivalentă din pairs_yoy."""
    if not pairs_curr:
        return []

    all_pairs = list(pairs_curr) + list(pairs_yoy)
    years = {y for (y, _m) in all_pairs}
    months = {m for (_y, m) in all_pairs}

    sales_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
        )
        .group_by(RawSale.year, RawSale.month)
    )
    sales_rows = _filter_pairs((await session.execute(sales_stmt)).all(), all_pairs)
    sales_map: dict[tuple[int, int], Decimal] = {}
    for r in sales_rows:
        sales_map[(int(r.year), int(r.month))] = Decimal(r.amt or 0)

    sku_stmt = (
        select(RawSale.year, RawSale.month, RawSale.product_id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .distinct()
    )
    sku_map: dict[tuple[int, int], set[UUID]] = {}
    for r in (await session.execute(sku_stmt)).all():
        ym = (int(r.year), int(r.month))
        if ym not in set(all_pairs):
            continue
        sku_map.setdefault(ym, set()).add(r.product_id)

    out: list[MonthSeries] = []
    for (yc, mc), (yp, mp) in zip(pairs_curr, pairs_yoy):
        out.append(MonthSeries(
            year=yc,
            month=mc,
            sales_curr=sales_map.get((yc, mc), Decimal(0)),
            sales_prev_year=sales_map.get((yp, mp), Decimal(0)),
            sku_curr=len(sku_map.get((yc, mc), set())),
            sku_prev_year=len(sku_map.get((yp, mp), set())),
        ))
    return out


async def _categories(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    store_id: UUID,
    sources: list[str],
    pairs_curr: list[tuple[int, int]],
    pairs_yoy: list[tuple[int, int]],
) -> list[CategoryRow]:
    """Breakdown pe categorie de produs, curent + YoY.

    - scope=adp  → ProductCategory.code (MU/EPS/UMEDE/VARSACI/DIBLURI etc.)
    - scope=sika → Target Market (Building Finishing / Sealing & Bonding /
      Waterproofing & Roofing / Concrete & Anchors / Flooring /
      Industry & Accessories / Altele) prin `classify_sika_tm(product.name)`
    """
    if not pairs_curr:
        return []
    if scope == "sika":
        return await _categories_sika(
            session, tenant_id,
            store_id=store_id, sources=sources,
            pairs_curr=pairs_curr, pairs_yoy=pairs_yoy,
        )

    all_pairs = list(pairs_curr) + list(pairs_yoy)
    years = {y for (y, _m) in all_pairs}
    months = {m for (_y, m) in all_pairs}

    # Sales + qty pe (year, month, category_id, category_code, category_label)
    sales_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            ProductCategory.code.label("cat_code"),
            ProductCategory.label.label("cat_label"),
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
        )
        .group_by(
            RawSale.year, RawSale.month,
            ProductCategory.code, ProductCategory.label,
        )
    )
    sales_rows = _filter_pairs((await session.execute(sales_stmt)).all(), all_pairs)

    # SKU distinct per categorie × window
    sku_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            ProductCategory.code.label("cat_code"),
            RawSale.product_id,
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .join(ProductCategory, ProductCategory.id == Product.category_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .distinct()
    )
    sku_curr_by_cat: dict[str, set[UUID]] = {}
    sku_yoy_by_cat: dict[str, set[UUID]] = {}
    pairs_curr_set = set(pairs_curr)
    pairs_yoy_set = set(pairs_yoy)
    for r in (await session.execute(sku_stmt)).all():
        ym = (int(r.year), int(r.month))
        code = str(r.cat_code)
        if ym in pairs_curr_set:
            sku_curr_by_cat.setdefault(code, set()).add(r.product_id)
        elif ym in pairs_yoy_set:
            sku_yoy_by_cat.setdefault(code, set()).add(r.product_id)

    rows: dict[str, CategoryRow] = {}
    for r in sales_rows:
        code = str(r.cat_code)
        label = str(r.cat_label or code)
        cr = rows.setdefault(code, CategoryRow(code=code, label=label))
        ym = (int(r.year), int(r.month))
        amt = Decimal(r.amt or 0)
        qty = Decimal(r.qty or 0)
        if ym in pairs_curr_set:
            cr.curr.sales += amt
            cr.curr.quantity += qty
        elif ym in pairs_yoy_set:
            cr.yoy.sales += amt
            cr.yoy.quantity += qty

    for code, cr in rows.items():
        cr.curr.sku_count = len(sku_curr_by_cat.get(code, set()))
        cr.yoy.sku_count = len(sku_yoy_by_cat.get(code, set()))

    out = list(rows.values())
    out.sort(key=lambda c: c.curr.sales, reverse=True)
    return out


async def _categories_sika(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store_id: UUID,
    sources: list[str],
    pairs_curr: list[tuple[int, int]],
    pairs_yoy: list[tuple[int, int]],
) -> list[CategoryRow]:
    """Sika variant — grupează pe Target Market (TM) derivat din numele
    produsului via `grupe_produse.classify_sika_tm`. „Altele" devine bucket-ul
    pentru produsele neclasificate (inclusiv non-Sika apărute pe batch Sika)."""
    from app.modules.grupe_produse.service import classify_sika_tm

    all_pairs = list(pairs_curr) + list(pairs_yoy)
    years = {y for (y, _m) in all_pairs}
    months = {m for (_y, m) in all_pairs}
    pairs_curr_set = set(pairs_curr)
    pairs_yoy_set = set(pairs_yoy)

    # Sales + qty pe (year, month, product_id), apoi clasificăm produsul în Python.
    sales_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            RawSale.product_id,
            Product.name.label("pname"),
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .group_by(RawSale.year, RawSale.month, RawSale.product_id, Product.name)
    )
    sales_rows = _filter_pairs((await session.execute(sales_stmt)).all(), all_pairs)

    rows: dict[str, CategoryRow] = {}
    sku_curr: dict[str, set[UUID]] = {}
    sku_yoy: dict[str, set[UUID]] = {}
    for r in sales_rows:
        tm = classify_sika_tm(str(r.pname or ""))
        ym = (int(r.year), int(r.month))
        amt = Decimal(r.amt or 0)
        qty = Decimal(r.qty or 0)
        cr = rows.setdefault(tm, CategoryRow(code=tm, label=tm))
        if ym in pairs_curr_set:
            cr.curr.sales += amt
            cr.curr.quantity += qty
            sku_curr.setdefault(tm, set()).add(r.product_id)
        elif ym in pairs_yoy_set:
            cr.yoy.sales += amt
            cr.yoy.quantity += qty
            sku_yoy.setdefault(tm, set()).add(r.product_id)

    for tm, cr in rows.items():
        cr.curr.sku_count = len(sku_curr.get(tm, set()))
        cr.yoy.sku_count = len(sku_yoy.get(tm, set()))

    out = list(rows.values())
    out.sort(key=lambda c: c.curr.sales, reverse=True)
    return out


async def _brand_split(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store_id: UUID,
    sources: list[str],
    pairs_curr: list[tuple[int, int]],
    pairs_yoy: list[tuple[int, int]],
) -> BrandSplit:
    """Brand vs Marcă Privată — `brands.is_private_label` decide."""
    if not pairs_curr:
        return BrandSplit()

    all_pairs = list(pairs_curr) + list(pairs_yoy)
    years = {y for (y, _m) in all_pairs}
    months = {m for (_y, m) in all_pairs}
    pairs_curr_set = set(pairs_curr)
    pairs_yoy_set = set(pairs_yoy)

    sales_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            Brand.is_private_label.label("is_pl"),
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .join(Brand, Brand.id == Product.brand_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
        )
        .group_by(RawSale.year, RawSale.month, Brand.is_private_label)
    )
    sales_rows = _filter_pairs((await session.execute(sales_stmt)).all(), all_pairs)

    sku_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            Brand.is_private_label.label("is_pl"),
            RawSale.product_id,
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .join(Brand, Brand.id == Product.brand_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .distinct()
    )
    sku_curr_pl: set[UUID] = set()
    sku_curr_brand: set[UUID] = set()
    sku_yoy_pl: set[UUID] = set()
    sku_yoy_brand: set[UUID] = set()
    for r in (await session.execute(sku_stmt)).all():
        ym = (int(r.year), int(r.month))
        is_pl = bool(r.is_pl)
        if ym in pairs_curr_set:
            (sku_curr_pl if is_pl else sku_curr_brand).add(r.product_id)
        elif ym in pairs_yoy_set:
            (sku_yoy_pl if is_pl else sku_yoy_brand).add(r.product_id)

    out = BrandSplit()
    for r in sales_rows:
        ym = (int(r.year), int(r.month))
        is_pl = bool(r.is_pl)
        amt = Decimal(r.amt or 0)
        qty = Decimal(r.qty or 0)
        if ym in pairs_curr_set:
            target = out.private_label if is_pl else out.brand
        elif ym in pairs_yoy_set:
            target = out.private_label_yoy if is_pl else out.brand_yoy
        else:
            continue
        target.sales += amt
        target.quantity += qty

    out.brand.sku_count = len(sku_curr_brand)
    out.private_label.sku_count = len(sku_curr_pl)
    out.brand_yoy.sku_count = len(sku_yoy_brand)
    out.private_label_yoy.sku_count = len(sku_yoy_pl)
    return out


async def _products(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    store_id: UUID,
    sources: list[str],
    pairs_curr: list[tuple[int, int]],
    pairs_yoy: list[tuple[int, int]],
) -> list[ProductRow]:
    """Top produse vândute la magazin în fereastra curentă, cu YoY.

    - scope=adp  → categoria = ProductCategory.code/label
    - scope=sika → categoria = TM derivat din clasificator (lazy import)
    Sortat desc după sales_curr. Toate produsele cu vânzări (sau qty) > 0
    în fereastra curentă sunt incluse — UI poate decide cap de afișare.
    """
    if not pairs_curr:
        return []
    all_pairs = list(pairs_curr) + list(pairs_yoy)
    years = {y for (y, _m) in all_pairs}
    months = {m for (_y, m) in all_pairs}
    pairs_curr_set = set(pairs_curr)
    pairs_yoy_set = set(pairs_yoy)

    sales_stmt = (
        select(
            RawSale.year,
            RawSale.month,
            RawSale.product_id,
            Product.code.label("p_code"),
            Product.name.label("p_name"),
            ProductCategory.code.label("cat_code"),
            ProductCategory.label.label("cat_label"),
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .join(Product, Product.id == RawSale.product_id)
        .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id == store_id,
            RawSale.year.in_(years),
            RawSale.month.in_(months),
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .group_by(
            RawSale.year, RawSale.month, RawSale.product_id,
            Product.code, Product.name,
            ProductCategory.code, ProductCategory.label,
        )
    )
    sales_rows = _filter_pairs((await session.execute(sales_stmt)).all(), all_pairs)

    classify = None
    if scope == "sika":
        from app.modules.grupe_produse.service import classify_sika_tm
        classify = classify_sika_tm

    rows: dict[UUID, ProductRow] = {}
    for r in sales_rows:
        pid = r.product_id
        if pid not in rows:
            cat_code = str(r.cat_code) if r.cat_code else None
            cat_label = str(r.cat_label) if r.cat_label else cat_code
            if classify is not None:
                tm = classify(str(r.p_name or ""))
                cat_code = tm
                cat_label = tm
            rows[pid] = ProductRow(
                product_id=pid,
                code=str(r.p_code or ""),
                name=str(r.p_name or ""),
                category_code=cat_code,
                category_label=cat_label,
            )
        ym = (int(r.year), int(r.month))
        amt = Decimal(r.amt or 0)
        qty = Decimal(r.qty or 0)
        target = rows[pid].curr if ym in pairs_curr_set else (
            rows[pid].yoy if ym in pairs_yoy_set else None
        )
        if target is None:
            continue
        target.sales += amt
        target.quantity += qty

    out = list(rows.values())
    out.sort(key=lambda p: p.curr.sales, reverse=True)
    return out


# ── Public entry point ───────────────────────────────────────────────────


async def build_dashboard(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    store_id: UUID,
    months_window: int = DEFAULT_MONTHS_WINDOW,
) -> DashboardData | None:
    """Construiește dashboard-ul complet pentru un magazin canonic."""
    sources = SCOPE_SOURCES.get(scope, [])
    if not sources:
        return None

    # Hidratăm numele magazinului.
    store_row = (await session.execute(
        select(Store.name).where(
            Store.tenant_id == tenant_id,
            Store.id == store_id,
        )
    )).first()
    if not store_row:
        return None
    store_name = str(store_row.name)

    latest = await _latest_month_with_data(
        session, tenant_id, sources=sources,
    )
    if not latest:
        return DashboardData(
            scope=scope, store_id=store_id, store_name=store_name,
            months_window=months_window,
            window_curr=[], window_yoy=[], window_prev=[],
            kpi_curr=Metrics(), kpi_yoy=Metrics(), kpi_prev=Metrics(),
            monthly=[], categories=[], brand_split=BrandSplit(),
        )

    pairs_curr = _window_pairs(latest, months_window)
    pairs_yoy = [(y - 1, m) for (y, m) in pairs_curr]
    earliest_curr = pairs_curr[0]
    prev_end = _shift(earliest_curr[0], earliest_curr[1], -1)
    pairs_prev = _window_pairs(prev_end, months_window)

    kpi_curr = await _aggregate_window(
        session, tenant_id, store_id=store_id, sources=sources, pairs=pairs_curr,
    )
    kpi_yoy = await _aggregate_window(
        session, tenant_id, store_id=store_id, sources=sources, pairs=pairs_yoy,
    )
    kpi_prev = await _aggregate_window(
        session, tenant_id, store_id=store_id, sources=sources, pairs=pairs_prev,
    )

    monthly = await _monthly_series(
        session, tenant_id, store_id=store_id, sources=sources,
        pairs_curr=pairs_curr, pairs_yoy=pairs_yoy,
    )
    categories = await _categories(
        session, tenant_id, scope=scope, store_id=store_id, sources=sources,
        pairs_curr=pairs_curr, pairs_yoy=pairs_yoy,
    )
    brand_split = await _brand_split(
        session, tenant_id, store_id=store_id, sources=sources,
        pairs_curr=pairs_curr, pairs_yoy=pairs_yoy,
    )
    products = await _products(
        session, tenant_id, scope=scope, store_id=store_id, sources=sources,
        pairs_curr=pairs_curr, pairs_yoy=pairs_yoy,
    )

    return DashboardData(
        scope=scope,
        store_id=store_id,
        store_name=store_name,
        months_window=months_window,
        window_curr=pairs_curr,
        window_yoy=pairs_yoy,
        window_prev=pairs_prev,
        kpi_curr=kpi_curr,
        kpi_yoy=kpi_yoy,
        kpi_prev=kpi_prev,
        monthly=monthly,
        categories=categories,
        brand_split=brand_split,
        products=products,
    )
