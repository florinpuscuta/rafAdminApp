"""
Price comparison service — KA (Key Accounts) vs TT (Traditional Trade),
plus analize KA-cross-KA (own / pret3net / propuneri listare) și KA vs Retail.

Agregă din `raw_sales` pe produs: preț mediu (sales/quantity) per canal/client.
Nu deține tabele proprii — e doar analitică read-only peste raw_sales.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sales.models import ImportBatch, RawSale


# Scoping pe batch.source — aceeași logică ca în `analiza_pe_luni` / `mortare`.
# adp   → doar batch-urile Adeplast (sales_xlsx)
# sika  → doar batch-urile Sika (sika_xlsx sau sika_mtd_xlsx)
# sikadp → amândouă (fără filtru)
_SOURCES_ADP: tuple[str, ...] = ("sales_xlsx",)
_SOURCES_SIKA: tuple[str, ...] = ("sika_xlsx", "sika_mtd_xlsx")


def _sources_for_company(company: str | None) -> tuple[str, ...] | None:
    """Returnează lista de surse pentru scoping, sau None pentru 'fără filtru'."""
    c = (company or "").lower()
    if c == "adeplast":
        return _SOURCES_ADP
    if c == "sika":
        return _SOURCES_SIKA
    return None


# Channel marker pentru KA. Dacă tenantul folosește alt string (ex "key-accounts",
# "KEY ACCOUNTS"), extinde lista; matching e case-insensitive.
_KA_CHANNEL_VALUES = ("KA", "KEY-ACCOUNTS", "KEY ACCOUNTS", "KEYACCOUNTS")
_RETAIL_CHANNEL_VALUES = ("RETAIL", "TRADITIONAL-RETAIL", "DIY")

# Liste KA canonice. Legacy folosea DEDEMAN / LEROY / HORNBACH / ALTEX (sau BRICO).
# Mapăm `client` (string brut din import) către una din aceste chei prin substring match.
KA_CLIENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "DEDEMAN": ("DEDEMAN",),
    "LEROY": ("LEROY", "LEROY MERLIN"),
    "HORNBACH": ("HORNBACH",),
    # Brico(store) e parte din grupul Altex — le unificăm sub aceeași cheie.
    "ALTEX": ("ALTEX", "BRICO", "BRICOSTORE", "BRICODEPOT"),
}
KA_CLIENT_KEYS = list(KA_CLIENT_PATTERNS.keys())


def _is_ka_channel(channel_col):
    """SQL expression: TRUE dacă `channel` e o formă de KA (UPPER + IN ...)."""
    return func.upper(func.coalesce(channel_col, "")).in_(_KA_CHANNEL_VALUES)


async def compare_ka_vs_tt(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    product_id: UUID | None = None,
    min_qty: Decimal = Decimal("0.01"),
    limit: int = 500,
) -> list[dict[str, Any]]:
    """
    Returnează o listă per-produs cu prețul mediu KA, TT, delta și volume.

    Gruparea e pe `description` când produsul nu e mapat canonic, altfel
    folosește `product_id` (mai stabil după redenumiri). Incluse doar
    produsele vândute în AMBELE canale (altfel comparația n-are sens).

    `min_qty` filtrează buckets cu volum prea mic (default 0.01 → permite tot).
    Crescut la 10+ în UI pentru medii mai credibile.
    """
    from app.modules.brands.models import Brand
    from app.modules.products.models import Product

    # Expresii reutilizabile
    ka_when_sales = case((_is_ka_channel(RawSale.channel), RawSale.amount), else_=0)
    ka_when_qty = case((_is_ka_channel(RawSale.channel), RawSale.quantity), else_=0)
    tt_when_sales = case((~_is_ka_channel(RawSale.channel), RawSale.amount), else_=0)
    tt_when_qty = case((~_is_ka_channel(RawSale.channel), RawSale.quantity), else_=0)

    # Gruparea se face pe `description` — e lizibil uman și funcționează chiar
    # când product_id nu e mapat (raw_sales.product_id poate fi NULL). Dacă
    # două linii au aceeași descriere dar product_id diferit, e semn că mapping-ul
    # de produs are duplicate — merge-ul canonicals le consolidează.
    stmt = (
        select(
            # product_id: cast-uim la text ca MAX să funcționeze (Postgres nu
            # are MAX(uuid) natural). Dacă toate liniile cu aceeași descriere
            # au același product_id, returnăm UUID-ul ca text.
            func.max(func.cast(RawSale.product_id, String)).label("product_id_text"),
            RawSale.product_name.label("description"),
            func.max(RawSale.product_code).label("product_code"),
            func.max(RawSale.category_code).label("category"),
            func.sum(ka_when_sales).label("ka_sales"),
            func.sum(ka_when_qty).label("ka_qty"),
            func.sum(tt_when_sales).label("tt_sales"),
            func.sum(tt_when_qty).label("tt_qty"),
            func.bool_or(Brand.is_private_label).label("is_private_label"),
        )
        .outerjoin(Product, Product.id == RawSale.product_id)
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.product_name.is_not(None),
            RawSale.product_name != "",
            RawSale.quantity > 0,
            RawSale.amount > 0,
        )
        .group_by(RawSale.product_name)
    )

    if year is not None:
        stmt = stmt.where(RawSale.year == year)
    if month is not None:
        stmt = stmt.where(RawSale.month == month)
    if category:
        # Match case-insensitive pe category_code (coloana de pe raw_sales)
        stmt = stmt.where(func.upper(RawSale.category_code) == category.upper())
    if product_id is not None:
        stmt = stmt.where(RawSale.product_id == product_id)

    # Doar produsele vândute pe ambele canale cu cantitate peste prag
    stmt = stmt.having(
        and_(
            func.sum(ka_when_qty) >= min_qty,
            func.sum(tt_when_qty) >= min_qty,
        )
    )

    # Sort: cea mai mare diferență absolută % mai sus (pune în evidență anomaliile)
    ka_price = func.sum(ka_when_sales) / func.nullif(func.sum(ka_when_qty), 0)
    tt_price = func.sum(tt_when_sales) / func.nullif(func.sum(tt_when_qty), 0)
    stmt = stmt.order_by(func.abs((ka_price - tt_price) / tt_price).desc()).limit(limit)

    result = await session.execute(stmt)
    rows: list[dict[str, Any]] = []
    for r in result.all():
        ka_sales_v = r.ka_sales or Decimal(0)
        ka_qty_v = r.ka_qty or Decimal(0)
        tt_sales_v = r.tt_sales or Decimal(0)
        tt_qty_v = r.tt_qty or Decimal(0)

        ka_p = (ka_sales_v / ka_qty_v) if ka_qty_v > 0 else None
        tt_p = (tt_sales_v / tt_qty_v) if tt_qty_v > 0 else None
        delta_abs = (ka_p - tt_p) if (ka_p is not None and tt_p is not None) else None
        delta_pct = (
            (ka_p - tt_p) / tt_p * 100
            if (ka_p is not None and tt_p is not None and tt_p > 0)
            else None
        )

        pid = None
        if r.product_id_text:
            try:
                pid = UUID(r.product_id_text)
            except (ValueError, TypeError):
                pid = None
        rows.append({
            "product_id": pid,
            "description": r.description,
            "product_code": r.product_code,
            "category": r.category,
            "ka_price": ka_p,
            "ka_qty": ka_qty_v,
            "ka_sales": ka_sales_v,
            "tt_price": tt_p,
            "tt_qty": tt_qty_v,
            "tt_sales": tt_sales_v,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "is_private_label": bool(r.is_private_label),
        })
    return rows


async def summary_ka_vs_tt(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """
    KPI-uri agregate pe TOATE produsele comparabile (nu doar top N).
    Util pentru header-ul paginii: "pe ansamblu, vinzi cu X% mai scump pe KA".
    """
    ka_when_sales = case((_is_ka_channel(RawSale.channel), RawSale.amount), else_=0)
    ka_when_qty = case((_is_ka_channel(RawSale.channel), RawSale.quantity), else_=0)
    tt_when_sales = case((~_is_ka_channel(RawSale.channel), RawSale.amount), else_=0)
    tt_when_qty = case((~_is_ka_channel(RawSale.channel), RawSale.quantity), else_=0)

    stmt = select(
        func.sum(ka_when_sales).label("ka_sales"),
        func.sum(ka_when_qty).label("ka_qty"),
        func.sum(tt_when_sales).label("tt_sales"),
        func.sum(tt_when_qty).label("tt_qty"),
    ).where(
        RawSale.tenant_id == tenant_id,
        RawSale.quantity > 0,
        RawSale.amount > 0,
    )

    if year is not None:
        stmt = stmt.where(RawSale.year == year)
    if month is not None:
        stmt = stmt.where(RawSale.month == month)
    if category:
        stmt = stmt.where(func.upper(RawSale.category_code) == category.upper())

    row = (await session.execute(stmt)).one_or_none()
    if row is None:
        return {"ka_avg_price": None, "tt_avg_price": None, "delta_pct": None,
                "ka_total_sales": Decimal(0), "tt_total_sales": Decimal(0)}

    ka_sales_v = row.ka_sales or Decimal(0)
    ka_qty_v = row.ka_qty or Decimal(0)
    tt_sales_v = row.tt_sales or Decimal(0)
    tt_qty_v = row.tt_qty or Decimal(0)

    ka_avg = (ka_sales_v / ka_qty_v) if ka_qty_v > 0 else None
    tt_avg = (tt_sales_v / tt_qty_v) if tt_qty_v > 0 else None
    delta_pct = (
        (ka_avg - tt_avg) / tt_avg * 100
        if (ka_avg is not None and tt_avg is not None and tt_avg > 0)
        else None
    )

    return {
        "ka_avg_price": ka_avg,
        "tt_avg_price": tt_avg,
        "delta_pct": delta_pct,
        "ka_total_sales": ka_sales_v,
        "tt_total_sales": tt_sales_v,
    }


# ────────────────────────────────────────────────────────────────────────────
# Utilitare comune pentru cele 3 analize "Prețuri KA"
# ────────────────────────────────────────────────────────────────────────────


def _ka_client_case():
    """SQL CASE care clasifică `RawSale.client` într-o cheie KA_CLIENT_KEYS.
    Returnează `NULL` când clientul nu matchează niciun pattern KA.
    Matching: UPPER(client) LIKE '%PATTERN%' pentru fiecare pattern.
    """
    whens = []
    for key, patterns in KA_CLIENT_PATTERNS.items():
        for p in patterns:
            whens.append((func.upper(RawSale.client).like(f"%{p}%"), key))
    return case(*whens, else_=None)


def _apply_ka_scope(stmt, *, tenant_id: UUID, year: int | None = None, months: list[int] | None = None):
    """Aplică filtrele comune: tenant, canal KA, an, luni, excluziuni."""
    stmt = stmt.where(
        RawSale.tenant_id == tenant_id,
        _is_ka_channel(RawSale.channel),
        RawSale.product_name.is_not(None),
        RawSale.product_name != "",
        RawSale.quantity > 0,
        RawSale.amount > 0,
    )
    if year is not None:
        stmt = stmt.where(RawSale.year == year)
    if months:
        stmt = stmt.where(RawSale.month.in_(months))
    return stmt


# ────────────────────────────────────────────────────────────────────────────
# 1. /prices/own — Prețuri cross-KA (propriu)
#    Per produs (al brandului propriu), prețul mediu la fiecare KA + min/max/spread.
# ────────────────────────────────────────────────────────────────────────────


async def cross_ka_own(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    months: list[int] | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Returnează, per produs, prețul mediu la fiecare dintre cele 4 KA.
    Util pentru a vedea dispersia de preț pentru același produs între magazine.
    """
    ka_key = _ka_client_case().label("ka_key")
    stmt = select(
        RawSale.product_name.label("description"),
        func.max(RawSale.product_code).label("product_code"),
        func.max(RawSale.category_code).label("category"),
        ka_key,
        func.sum(RawSale.amount).label("sales"),
        func.sum(RawSale.quantity).label("qty"),
    ).group_by(RawSale.product_name, ka_key)

    stmt = _apply_ka_scope(stmt, tenant_id=tenant_id, year=year, months=months)
    stmt = stmt.where(ka_key.is_not(None))
    if category:
        stmt = stmt.where(func.upper(RawSale.category_code) == category.upper())

    result = await session.execute(stmt)

    # Grupare în memorie: description → {ka_key: {sales, qty}}
    products: dict[str, dict[str, Any]] = {}
    for r in result.all():
        desc = r.description
        if desc not in products:
            products[desc] = {
                "description": desc,
                "product_code": r.product_code,
                "category": r.category,
                "prices": {},
            }
        sales_v = r.sales or Decimal(0)
        qty_v = r.qty or Decimal(0)
        price = (sales_v / qty_v) if qty_v > 0 else None
        products[desc]["prices"][r.ka_key] = {
            "price": price,
            "qty": qty_v,
            "sales": sales_v,
        }

    # Calcul min/max/spread per produs + filtrare produse cu cel puțin 2 KA
    rows: list[dict[str, Any]] = []
    for p in products.values():
        valid = [v["price"] for v in p["prices"].values() if v["price"] is not None and v["price"] > 0]
        if len(valid) < 2:
            continue
        mn = min(valid)
        mx = max(valid)
        spread_pct = ((mx - mn) / mn * 100) if mn > 0 else None
        p["min_price"] = mn
        p["max_price"] = mx
        p["spread_pct"] = spread_pct
        p["n_stores"] = len(valid)
        rows.append(p)

    # Sort: cel mai mare spread întâi (produsele cu dispersie mare = ținte de analiză)
    rows.sort(key=lambda x: -(x["spread_pct"] or Decimal(0)))

    return {"ka_clients": KA_CLIENT_KEYS, "rows": rows}


# ────────────────────────────────────────────────────────────────────────────
# 2. /prices/pret3net — Preț 3 Net Comp KA
#    Per produs, per KA client: preț mediu (sales/qty). Discount-ul se aplică
#    client-side (recalcul live în frontend).
# ────────────────────────────────────────────────────────────────────────────


async def pret3net(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    months: list[int] | None = None,
    company: str = "adeplast",
) -> dict[str, Any]:
    """Pentru fiecare produs+KA: sales, qty, preț mediu — grupat pe categorie.

    Scoping via `ImportBatch.source` (ca în `analiza_pe_luni` / `mortare`):
      - adeplast → doar batch-uri `sales_xlsx`
      - sika     → doar batch-uri `sika_xlsx` / `sika_mtd_xlsx`
      - sikadp   → fără filtru (ambele)
    """
    from app.modules.brands.models import Brand
    from app.modules.products.models import Product

    ka_key = _ka_client_case().label("ka_key")
    stmt = select(
        RawSale.category_code.label("category"),
        RawSale.product_name.label("description"),
        ka_key,
        func.sum(RawSale.amount).label("sales"),
        func.sum(RawSale.quantity).label("qty"),
        func.bool_or(Brand.is_private_label).label("is_private_label"),
    ).outerjoin(
        Product, Product.id == RawSale.product_id,
    ).outerjoin(
        Brand, Brand.id == Product.brand_id,
    ).group_by(RawSale.category_code, RawSale.product_name, ka_key)

    stmt = _apply_ka_scope(stmt, tenant_id=tenant_id, year=year, months=months)
    stmt = stmt.where(ka_key.is_not(None))
    stmt = stmt.where(RawSale.category_code.is_not(None), RawSale.category_code != "")

    # Brand/company scope via batch source
    sources = _sources_for_company(company)
    if sources:
        stmt = stmt.join(ImportBatch, ImportBatch.id == RawSale.batch_id).where(
            ImportBatch.source.in_(sources)
        )

    result = await session.execute(stmt)

    # Agregă: category → description → ka_key → {sales, qty, price}
    by_cat: dict[str, dict[str, dict[str, Any]]] = {}
    for r in result.all():
        cat = r.category or "ALTELE"
        desc = r.description
        if cat not in by_cat:
            by_cat[cat] = {}
        if desc not in by_cat[cat]:
            by_cat[cat][desc] = {
                "description": desc,
                "clients": {},
                "total_sales": Decimal(0),
                "total_qty": Decimal(0),
                "is_private_label": bool(r.is_private_label),
            }
        elif r.is_private_label:
            by_cat[cat][desc]["is_private_label"] = True
        sales_v = r.sales or Decimal(0)
        qty_v = r.qty or Decimal(0)
        price = (sales_v / qty_v) if qty_v > 0 else None
        by_cat[cat][desc]["clients"][r.ka_key] = {
            "sales": sales_v,
            "qty": qty_v,
            "price": price,
        }
        by_cat[cat][desc]["total_sales"] += sales_v
        by_cat[cat][desc]["total_qty"] += qty_v

    # Convertește dict → list, sortat pe total_sales desc
    categories: dict[str, list[dict[str, Any]]] = {}
    for cat, prods in by_cat.items():
        lst = sorted(prods.values(), key=lambda p: -(p["total_sales"] or Decimal(0)))
        categories[cat] = lst

    return {
        "year": year,
        "ka_clients": KA_CLIENT_KEYS,
        "categories": categories,
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. /prices/propuneri — Propuneri Listare KA
#    Pentru fiecare KA, lista produselor vândute la alte KA dar NU la acesta.
# ────────────────────────────────────────────────────────────────────────────


async def propuneri_listare(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    months: list[int] | None = None,
    company: str = "adeplast",
) -> dict[str, Any]:
    """Pentru fiecare KA: produsele nelistate dar vândute la alte KA, cu preț
    minim dintre celelalte rețele ca referință.

    Exclude mereu produsele de marca privată (`Brand.is_private_label=True`)
    — nu are sens comercial să le propunem spre listare la alte rețele.

    Scoping via `ImportBatch.source`:
      - adeplast → `sales_xlsx`
      - sika     → `sika_xlsx` / `sika_mtd_xlsx`
      - sikadp   → ambele
    """
    from app.modules.brands.models import Brand
    from app.modules.products.models import Product

    ka_key = _ka_client_case().label("ka_key")
    stmt = select(
        RawSale.category_code.label("category"),
        RawSale.product_name.label("description"),
        ka_key,
        func.sum(RawSale.amount).label("sales"),
        func.sum(RawSale.quantity).label("qty"),
    ).group_by(RawSale.category_code, RawSale.product_name, ka_key)

    stmt = _apply_ka_scope(stmt, tenant_id=tenant_id, year=year, months=months)
    stmt = stmt.where(ka_key.is_not(None))
    stmt = stmt.where(RawSale.category_code.is_not(None), RawSale.category_code != "")

    # Brand/company scope via batch source
    sources = _sources_for_company(company)
    if sources:
        stmt = stmt.join(ImportBatch, ImportBatch.id == RawSale.batch_id).where(
            ImportBatch.source.in_(sources)
        )

    # Exclude private label via flag canonic (Brand.is_private_label).
    # Rândurile cu product_id NULL nu sunt marca privată (backfill-ul le-a
    # rezolvat pe toate cele cu product_code valid), deci trec.
    private_subq = (
        select(Product.id)
        .join(Brand, Brand.id == Product.brand_id)
        .where(
            Product.tenant_id == tenant_id,
            Brand.is_private_label.is_(True),
        )
    )
    stmt = stmt.where(
        (RawSale.product_id.is_(None)) | (~RawSale.product_id.in_(private_subq))
    )

    result = await session.execute(stmt)

    # Construiește: (cat, desc) → {ka_key: {sales, qty}}
    products: dict[tuple[str, str], dict[str, dict[str, Decimal]]] = {}
    for r in result.all():
        key = (r.category or "", r.description)
        if key not in products:
            products[key] = {}
        sales_v = r.sales or Decimal(0)
        qty_v = r.qty or Decimal(0)
        products[key][r.ka_key] = {"sales": sales_v, "qty": qty_v}

    suggestions: dict[str, list[dict[str, Any]]] = {k: [] for k in KA_CLIENT_KEYS}
    for ka in KA_CLIENT_KEYS:
        for (cat, desc), clients in products.items():
            # Skip dacă produsul e deja vândut la acest KA
            if ka in clients and (clients[ka]["sales"] or 0) > 0:
                continue
            # Calculează preț la ceilalți KA
            other_prices: dict[str, Decimal] = {}
            total_sales = Decimal(0)
            total_qty = Decimal(0)
            for other_ka, d in clients.items():
                if other_ka == ka:
                    continue
                if d["sales"] > 0 and d["qty"] > 0:
                    other_prices[other_ka] = d["sales"] / d["qty"]
                    total_sales += d["sales"]
                    total_qty += d["qty"]
            if not other_prices:
                continue
            min_price = min(other_prices.values())
            min_ka = next(k for k, v in other_prices.items() if v == min_price)
            suggestions[ka].append({
                "category": cat,
                "description": desc,
                "total_sales": total_sales,
                "total_qty": total_qty,
                "min_price": min_price,
                "min_price_ka": min_ka,
                "prices": {k: v for k, v in other_prices.items()},
                "num_kas": len(other_prices),
            })
        suggestions[ka].sort(key=lambda x: -(x["total_sales"] or Decimal(0)))

    return {
        "year": year,
        "ka_clients": KA_CLIENT_KEYS,
        "suggestions": suggestions,
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. /prices/ka-retail — Top produse KA vs Retail
#    Ca /ka-vs-tt, dar distinge strict channel='RETAIL' (nu "orice non-KA").
# ────────────────────────────────────────────────────────────────────────────


def _is_retail_channel(channel_col):
    return func.upper(func.coalesce(channel_col, "")).in_(_RETAIL_CHANNEL_VALUES)


async def ka_vs_retail(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    months: list[int] | None = None,
    category: str | None = None,
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Top N produse vândute atât pe KA cât și Retail, cu prețuri medii."""
    from app.modules.brands.models import Brand
    from app.modules.products.models import Product

    ka_sales_expr = case((_is_ka_channel(RawSale.channel), RawSale.amount), else_=0)
    ka_qty_expr = case((_is_ka_channel(RawSale.channel), RawSale.quantity), else_=0)
    rt_sales_expr = case((_is_retail_channel(RawSale.channel), RawSale.amount), else_=0)
    rt_qty_expr = case((_is_retail_channel(RawSale.channel), RawSale.quantity), else_=0)

    stmt = select(
        RawSale.product_name.label("description"),
        func.max(RawSale.product_code).label("product_code"),
        func.max(RawSale.category_code).label("category"),
        func.sum(ka_sales_expr).label("ka_sales"),
        func.sum(ka_qty_expr).label("ka_qty"),
        func.sum(rt_sales_expr).label("rt_sales"),
        func.sum(rt_qty_expr).label("rt_qty"),
        (func.sum(ka_sales_expr) + func.sum(rt_sales_expr)).label("total_sales"),
        func.bool_or(Brand.is_private_label).label("is_private_label"),
    ).outerjoin(
        Product, Product.id == RawSale.product_id,
    ).outerjoin(
        Brand, Brand.id == Product.brand_id,
    ).where(
        RawSale.tenant_id == tenant_id,
        RawSale.product_name.is_not(None),
        RawSale.product_name != "",
    ).group_by(RawSale.product_name)

    if year is not None:
        stmt = stmt.where(RawSale.year == year)
    if months:
        stmt = stmt.where(RawSale.month.in_(months))
    if category:
        stmt = stmt.where(func.upper(RawSale.category_code) == category.upper())

    # Doar produse vândute în AMBELE canale
    stmt = stmt.having(
        and_(
            func.sum(ka_qty_expr) > 0,
            func.sum(rt_qty_expr) > 0,
        )
    )
    stmt = stmt.order_by(
        (func.sum(ka_sales_expr) + func.sum(rt_sales_expr)).desc()
    ).limit(limit)

    result = await session.execute(stmt)
    rows: list[dict[str, Any]] = []
    for r in result.all():
        ka_sales_v = r.ka_sales or Decimal(0)
        ka_qty_v = r.ka_qty or Decimal(0)
        rt_sales_v = r.rt_sales or Decimal(0)
        rt_qty_v = r.rt_qty or Decimal(0)
        ka_price = (ka_sales_v / ka_qty_v) if ka_qty_v > 0 else None
        rt_price = (rt_sales_v / rt_qty_v) if rt_qty_v > 0 else None
        diff_pct = (
            (ka_price - rt_price) / rt_price * 100
            if (ka_price is not None and rt_price is not None and rt_price > 0)
            else None
        )
        rows.append({
            "description": r.description,
            "product_code": r.product_code,
            "category": r.category,
            "ka_sales": ka_sales_v,
            "ka_qty": ka_qty_v,
            "ka_price": ka_price,
            "retail_sales": rt_sales_v,
            "retail_qty": rt_qty_v,
            "retail_price": rt_price,
            "diff_pct": diff_pct,
            "total_sales": r.total_sales or Decimal(0),
            "is_private_label": bool(r.is_private_label),
        })
    return rows


# ─────────────────────────────────────────────────────────────────────────
# Port LEGACY Prețuri Comparative + Adeplast/Sika cross-KA
# ─────────────────────────────────────────────────────────────────────────

from sqlalchemy import select as _select  # re-import local alias
from app.modules.prices.models import PriceGridRow, PriceGridMeta


async def get_price_grid(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store: str,
    company: str = "adeplast",
) -> dict:
    """Port 1:1 al legacy `api_price_grid_get` din routes/pricing.py:378."""
    rows = (await session.execute(
        _select(PriceGridRow)
        .where(
            PriceGridRow.tenant_id == tenant_id,
            PriceGridRow.company == company,
            PriceGridRow.store == store,
        )
        .order_by(PriceGridRow.row_idx)
    )).scalars().all()

    meta_row = (await session.execute(
        _select(PriceGridMeta)
        .where(
            PriceGridMeta.tenant_id == tenant_id,
            PriceGridMeta.company == company,
            PriceGridMeta.store == store,
        )
    )).scalar_one_or_none()

    meta = {
        "store": store,
        "date_prices": meta_row.date_prices if meta_row else None,
        "brands": meta_row.brands if meta_row else [],
        "imported_at": meta_row.imported_at.isoformat() if meta_row else None,
        "imported_by": meta_row.imported_by if meta_row else None,
    }
    return {
        "store": store,
        "meta": meta,
        "rows": [
            {
                "id": str(r.id),
                "row_idx": r.row_idx,
                "row_num": r.row_num,
                "group_label": r.group_label,
                "brand_data": r.brand_data,
            }
            for r in rows
        ],
    }


_LEGACY_KA_STORES = ["Dedeman", "Leroy", "Hornbach", "Brico"]


def _norm_product(name: str | None) -> str:
    """Normalizare pentru matching (port din legacy)."""
    import re as _re
    if not name:
        return ""
    s = name.upper()
    s = _re.sub(r"\s+", " ", s).strip()
    s = s.replace("-", "").replace(".", "")
    s = _re.sub(r"(\d+)\s*KG", r"\1KG", s)
    s = _re.sub(r"(\d+)\s*GR", r"\1GR", s)
    return s


def _norm_for_category(name: str | None) -> str:
    """Normalizare agresivă pentru match nume → categorie produs canonic.
    Strip spații, punctuație, diacritice, uppercase.
    """
    import re as _re
    if not name:
        return ""
    s = name.upper()
    repl = str.maketrans({
        "Ş": "S", "Ș": "S", "Ţ": "T", "Ț": "T",
        "Ă": "A", "Â": "A", "Î": "I",
    })
    s = s.translate(repl)
    s = _re.sub(r"[^A-Z0-9]", "", s)
    return s


_DIACRITICS_TRANSLATE = str.maketrans({
    "Ş": "S", "Ș": "S", "ş": "s", "ș": "s",
    "Ţ": "T", "Ț": "T", "ţ": "t", "ț": "t",
    "Ă": "A", "ă": "a", "Â": "A", "â": "a",
    "Î": "I", "î": "i",
})


def _strip_diacritics(s: str) -> str:
    return s.translate(_DIACRITICS_TRANSLATE) if s else s


async def _resolve_label_categories(
    session: AsyncSession, tenant_id: UUID, labels: set[str],
) -> dict[str, dict]:
    """Pentru fiecare label din price_grid, gaseste produsul canonic cel mai
    similar (pg_trgm similarity peste nume) si returneaza categoria asociata.

    Asigura ca toate produsele cross-KA au categorie — match-uirea cade pe
    nearest-neighbor cand exact match nu exista."""
    from sqlalchemy import text as _text

    if not labels:
        return {}

    # Incarca o singura data toate produsele tenant-ului si calculeaza
    # similaritatea per label in DB (SELECT-uri scurte, dar evitam un JOIN
    # array care nu merge clean cu asyncpg).
    out: dict[str, dict] = {}
    for lbl in labels:
        norm = _strip_diacritics(lbl).upper()
        row = (await session.execute(
            _text("""
            SELECT pc.code, pc.label
            FROM products p
            JOIN product_categories pc ON pc.id = p.category_id
            WHERE p.tenant_id = :tid
              AND p.category_id IS NOT NULL
            ORDER BY similarity(:lbl, upper(p.name)) DESC
            LIMIT 1
            """),
            {"tid": str(tenant_id), "lbl": norm},
        )).first()
        if row:
            out[lbl] = {"code": row[0], "label": row[1]}
    return out


async def update_price_grid_cell(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    store: str,
    company: str,
    row_idx: int,
    brand: str,
    prod: str | None = None,
    pret: float | str | None = None,
) -> bool:
    """Update manual pentru o celulă — port legacy PUT /api/price_grid/<store>/cell.

    Când `pret` e setat → marchează celula cu ai_status='manual' (punct albastru).
    """
    from sqlalchemy import select as _sel, update as _upd
    from datetime import datetime as _dt

    row = (await session.execute(
        _sel(PriceGridRow).where(
            PriceGridRow.tenant_id == tenant_id,
            PriceGridRow.company == company,
            PriceGridRow.store == store,
            PriceGridRow.row_idx == row_idx,
        )
    )).scalar_one_or_none()
    if row is None:
        return False

    bd = dict(row.brand_data or {})
    cell = dict(bd.get(brand) or {})
    if prod is not None:
        stripped = (prod or "").strip()
        cell["prod"] = stripped or None
    if pret is not None:
        # Parsing: empty/None/"-" → null
        if pret in ("", "-", None):
            cell["pret"] = None
        else:
            try:
                cell["pret"] = float(pret)
            except (TypeError, ValueError):
                cell["pret"] = None
        # Marchează manual
        cell["ai_status"] = "manual"
        cell["ai_updated_at"] = _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cell.pop("ai_reason", None)
        cell.pop("ai_url", None)
    bd[brand] = cell

    await session.execute(
        _upd(PriceGridRow).where(PriceGridRow.id == row.id).values(brand_data=bd)
    )
    await session.commit()
    return True


async def get_own_cross_ka(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    company: str = "adeplast",
) -> dict:
    """Port 1:1 al legacy `api_price_grid_own_cross_ka` din routes/pricing.py:496.

    Tabel pivot: produsele proprii × 4 rețele KA.
    """
    own_brand = "sika" if company == "sika" else "adeplast"

    # 1. Load all rows for 4 KA stores
    all_rows: dict[str, list[dict]] = {}
    for store in _LEGACY_KA_STORES:
        rows = (await session.execute(
            _select(PriceGridRow.row_idx, PriceGridRow.row_num, PriceGridRow.brand_data)
            .where(
                PriceGridRow.tenant_id == tenant_id,
                PriceGridRow.company == company,
                PriceGridRow.store == store,
            )
            .order_by(PriceGridRow.row_idx)
        )).all()
        all_rows[store] = []
        for r in rows:
            bd = r.brand_data or {}
            # Găsește celula brandului propriu (case-insensitive)
            own_cell = None
            for k, v in bd.items():
                if k.lower().strip() == own_brand:
                    own_cell = v
                    break
            if own_cell and (own_cell.get("prod") or own_cell.get("pret") is not None):
                all_rows[store].append({
                    "row_idx": r.row_idx,
                    "row_num": r.row_num,
                    "prod": own_cell.get("prod") or "",
                    "pret": own_cell.get("pret"),
                    "ai_status": own_cell.get("ai_status"),
                    "ai_updated_at": own_cell.get("ai_updated_at"),
                })

    # 2. Pivot by normalized name
    by_norm: dict[str, dict] = {}
    for store in _LEGACY_KA_STORES:
        for row in all_rows.get(store, []):
            norm = _norm_product(row["prod"])
            if not norm:
                continue
            if norm not in by_norm:
                by_norm[norm] = {"canonical_name": row["prod"], "prices": {}}
            by_norm[norm]["prices"][store] = {
                "prod": row["prod"],
                "pret": row["pret"],
                "ai_status": row.get("ai_status"),
                "ai_updated_at": row.get("ai_updated_at"),
            }

    # 3. Compute min/max/spread per product
    distinct_labels = {data["canonical_name"] for data in by_norm.values()
                       if data.get("canonical_name")}
    cat_by_label = await _resolve_label_categories(session, tenant_id, distinct_labels)
    products = []
    for data in by_norm.values():
        prices_only = [
            float(p["pret"]) for p in data["prices"].values()
            if p.get("pret") is not None and p["pret"] > 0
        ]
        if prices_only:
            mn = min(prices_only)
            mx = max(prices_only)
            spread = ((mx - mn) / mn * 100) if mn > 0 else 0
        else:
            mn = mx = 0
            spread = 0
        cat = cat_by_label.get(data["canonical_name"])
        products.append({
            "canonical_name": data["canonical_name"],
            "prices": data["prices"],
            "min_price": round(mn, 2),
            "max_price": round(mx, 2),
            "spread_pct": round(spread, 2),
            "category_code": cat["code"] if cat else None,
            "category_label": cat["label"] if cat else None,
        })

    # Sort: descending by spread (most interesting first), then by canonical_name
    products.sort(key=lambda p: (-p["spread_pct"], p["canonical_name"]))

    return {
        "brand": "Adeplast" if own_brand == "adeplast" else "Sika",
        "stores": _LEGACY_KA_STORES,
        "products": products,
    }
