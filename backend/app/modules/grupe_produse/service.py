"""
"Grupe Produse" — breakdown vânzări KA per PRODUS într-o categorie (grup).

Pentru fiecare produs mapat (cu `product_id` și `category_id` = grup cerut):
  - sales_y1 / qty_y1  = an precedent (year-1)
  - sales_y2 / qty_y2  = an curent (year)
  - diff / pct         = Y2 − Y1 și procentul variației
  - price_y1 / price_y2 = sales / qty (None dacă qty = 0)

Plus totaluri pe grup (întreaga categorie).

Surse per scope — identic cu `analiza_pe_luni` (dedup în interiorul grupului
de sursă, grupurile se însumează):
  - adp    → [["sales_xlsx"]]
  - sika   → [["sika_mtd_xlsx", "sika_xlsx"]]
  - sikadp → [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]]

Rezolvarea canonică nu e necesară aici (nu agrupăm pe agent/store) — filtrăm
doar pe categoria produsului.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brands.models import Brand
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale


_GROUPS_ADP: list[list[str]] = [["sales_xlsx"]]
_GROUPS_SIKA: list[list[str]] = [["sika_mtd_xlsx", "sika_xlsx"]]
_GROUPS_SIKADP: list[list[str]] = [
    ["sales_xlsx"],
    ["sika_mtd_xlsx", "sika_xlsx"],
]


@dataclass
class ProductRow:
    product_id: UUID
    product_code: str
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


async def _sales_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    category_id: UUID,
    batch_source_groups: list[list[str]],
) -> list[dict[str, Any]]:
    """Rânduri agregate pe (product_id, year) pentru KA în categoria dată.

    Grupurile sunt disjuncte (se însumează). În cadrul unui grup, prioritatea
    e în ordinea listei — per (year, month) doar primul source cu date.
    """
    year_prev = year_curr - 1
    out: dict[tuple[UUID, int], dict[str, Any]] = {}

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
                if ym not in new_pairs:
                    continue
                if r.product_id is None:
                    continue
                key = (r.product_id, int(r.year))
                row = out.setdefault(key, {
                    "product_id": r.product_id,
                    "year": int(r.year),
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


# ── Core aggregation ─────────────────────────────────────────────────────


async def _build_products(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    category_id: UUID,
    batch_source_groups: list[list[str]],
) -> list[ProductRow]:
    year_prev = year_curr - 1

    rows = await _sales_rows(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=batch_source_groups,
    )

    by_product: dict[UUID, ProductRow] = {}
    product_ids: set[UUID] = set()
    for r in rows:
        pid = r["product_id"]
        product_ids.add(pid)
        pr = by_product.setdefault(
            pid,
            ProductRow(product_id=pid, product_code="", product_name=""),
        )
        if r["year"] == year_prev:
            pr.sales_y1 += r["amount"]
            pr.qty_y1 += r["quantity"]
        elif r["year"] == year_curr:
            pr.sales_y2 += r["amount"]
            pr.qty_y2 += r["quantity"]

    meta = await _hydrate_products(session, tenant_id, product_ids)
    for pid, pr in by_product.items():
        code, name = meta.get(pid, ("", ""))
        pr.product_code = code or ""
        pr.product_name = name or ""

    # Sortare: produse cu vânzări Y2 desc, apoi Y1 desc, apoi nume.
    def _sort_key(p: ProductRow) -> tuple[Decimal, Decimal, str]:
        return (-p.sales_y2, -p.sales_y1, p.product_name.lower())

    return sorted(by_product.values(), key=_sort_key)


# ── Public entry-points ──────────────────────────────────────────────────


async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID,
) -> dict[str, Any]:
    products = await _build_products(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_ADP,
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
    }


async def get_for_sika(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID,
) -> dict[str, Any]:
    products = await _build_products(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_SIKA,
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
    }


async def get_for_sikadp(
    session: AsyncSession, tenant_id: UUID, *,
    year_curr: int, category_id: UUID,
) -> dict[str, Any]:
    products = await _build_products(
        session, tenant_id,
        year_curr=year_curr, category_id=category_id,
        batch_source_groups=_GROUPS_SIKADP,
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
    }


async def list_categories(session: AsyncSession) -> list[dict[str, Any]]:
    """Listează toate categoriile disponibile (global) — folosite pentru
    selectorul din UI.
    """
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


# ── Tree view: Brand → Categorie → Produs ────────────────────────────────


_SCOPE_GROUPS: dict[str, list[list[str]]] = {
    "adp": _GROUPS_ADP,
    "sika": _GROUPS_SIKA,
    "sikadp": _GROUPS_SIKADP,
}


# Sika TM (Target Markets) — clasificare specifică Sika pentru arborele
# de produse în scope=sika. Primul pattern match câștigă; fallback "Altele".
# Ordinea contează: patterns mai specifice vin primele.
import re as _re

_SIKA_TM_RULES: list[tuple[str, _re.Pattern[str]]] = [
    # Rândurile "Customer Bonus <TM>" — redirecționăm direct după sufix.
    ("Building Finishing", _re.compile(r"CUSTOMER\s+BONUS\s+BUILDING", _re.I)),
    ("Sealing & Bonding", _re.compile(r"CUSTOMER\s+BONUS\s+SEALING", _re.I)),
    ("Waterproofing & Roofing", _re.compile(r"CUSTOMER\s+BONUS\s+(WATERPROOF|ROOFING|REFURB)", _re.I)),
    ("Concrete & Anchors", _re.compile(r"CUSTOMER\s+BONUS\s+CONCRETE", _re.I)),
    ("Flooring", _re.compile(r"CUSTOMER\s+BONUS\s+FLOORING", _re.I)),

    ("Flooring", _re.compile(
        r"SIKA\s*FLOOR|SIKA\s*SCREED|SIKA\s*LEVEL|"
        r"S\s*-?\s*DRAIN|S\s*-?\s*SCUPPER|AIR\s*VENT|"
        r"WATER\s*OUTLET|PIPE\s*CONNECTION|CAP\s+FOR\s+WATER",
        _re.I,
    )),
    ("Waterproofing & Roofing", _re.compile(
        r"LASTIC|IGOL\s*FLEX|IGASOL|SARNA\s*VAP|SARNA\s*FIL|SARNA\s*COL|"
        r"SIKA\s*PROOF|TOP\s*SEAL|SIKA\s*SWELL|SIKA\s*MUR|SIKA\s*WATERBAR|"
        r"SIKA\s*WRAP|WATER\s*BAR|SIKA\s*DUR|SIKA\s*-?\s*1\b|ICOSIT|"
        r"ARCO\s*(BITU|ELAST|SUPER|FORATO|THERMO)|ARTEC\s*\d|ARMEX|"
        r"DECOBIT|ECOBIT|ELASTECH|FESTA\s+PLUS|"
        r"SSH\s*(E|P|EKV|MG)|SIKA\s*-?\s*TROCAL|"
        r"SR\s*(ADHESIVE|CLEANER|CORNER)|"
        r"SIKA\s*(ANTISOL|CONTROL|PLAST|VISCO|EMACO|TOP\b|WT\b|-4A|GRUND)|"
        r"MASTER\s*EMACO|METAL\s+SHEET",
        _re.I,
    )),
    ("Concrete & Anchors", _re.compile(
        r"ANCHOR\s*FIX|SIKA\s*GROUT|MONO\s*TOP|SIKA\s*GARD|SIKA\s*PLASTIMENT|"
        r"SIKA\s*LPS|SIKA\s*VZ|SIKA\s*FS|SIKA\s*CEM|SIKA\s*COSMETIC|"
        r"SIKA\s*BETON|SIKA\s*LATEX|SIKA\s*PUMP",
        _re.I,
    )),
    ("Sealing & Bonding", _re.compile(
        r"SIKA\s*(FLEX|SIL|BOND|TACK|BLACK\s*SEAL|BOOM|MULTI\s*SEAL|"
        r"SEAL(TAPE|-)?|MAX\s*TACK|ACRYL|CRYL)|SIKA\s*BLACK|SIKAMAX|"
        r"SIKA\s*SEAL|SANISIL|FUGENHINTER",
        _re.I,
    )),
    ("Building Finishing", _re.compile(
        r"SIKA\s*CERAM|TILE\s*BOND|SIKA\s*WALL|SIKA\s*HOME|SIKA\s*THERM|"
        r"INSULATE|SIKA\s*GREEN",
        _re.I,
    )),
    ("Industry & Accessories", _re.compile(
        r"SIKA\s*PRIMER|AKTIVATOR|ACTIVATOR|SIKA\s*FIBER|QUARTZ|SF\s*TS|"
        r"SIKA\s*LAYER|S\s*-?\s*GLASS|S\s*-?\s*FELT|SPL\b|SOLVENT|"
        r"INJECTION|SIKA\s*SCHA?L|PACKER|PALLET|\bIBC\b|\bROL\b|"
        r"SIKA\s*COLOR|SIKA\s*SET|SIKA\s*(THINNER|COR|SEPAROL|STELL|"
        r"CARBO|COLMA|GRUND)|HARDRUBBER|DORR|DÖRR|SIKA\s*TR\s*\d|"
        r"DISCOUNT|FREIGHT|CHARGES",
        _re.I,
    )),
]


def _classify_sika_tm(name: str | None) -> str:
    n = name or ""
    for label, pat in _SIKA_TM_RULES:
        if pat.search(n):
            return label
    return "Altele"


_EPS_CLASS_RE = _re.compile(r"[Ee][Pp][Ss][ _\-]*(\d{2,3})")


def _eps_subgroup(name: str | None) -> tuple[str, str]:
    """(key, label) pentru subgrupa EPS extrasă din numele produsului.

    Ex: "BAUDEMAN EPS 80 100MM" → ("80", "EPS 80").
    Produse fără număr după "EPS" → ("unknown", "Fără clasă").
    """
    m = _EPS_CLASS_RE.search(name or "")
    if not m:
        return ("unknown", "Fără clasă")
    cls = m.group(1)
    return (cls, f"EPS {cls}")


def _build_eps_subgroups(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grupează produsele EPS după clasa extrasă din nume (50, 70, 80, ...).
    Returnează o listă sortată DESC după vânzări."""
    buckets: dict[str, dict[str, Any]] = {}
    for p in products:
        key, label = _eps_subgroup(p["name"])
        sb = buckets.setdefault(key, {
            "key": key,
            "label": label,
            "sales": Decimal(0),
            "qty": Decimal(0),
            "sales_prev": Decimal(0),
            "qty_prev": Decimal(0),
            "products": [],
        })
        sb["sales"] += p["sales"]
        sb["qty"] += p["qty"]
        sb["sales_prev"] += p["sales_prev"]
        sb["qty_prev"] += p["qty_prev"]
        sb["products"].append(p)
    out = list(buckets.values())
    out.sort(key=lambda s: (-s["sales"], s["label"].lower()))
    return out


async def build_tree(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    year: int,
    months: list[int] | None = None,
) -> dict[str, Any]:
    """Construiește un arbore Brand → Categorie → Produs pentru anul dat.

    Comparație:
      - dacă `months` e specificat (non-empty) → restrânge la acele luni
      - dacă `months` e None → auto-YTD: detectează lunile cu date în `year`
      - dacă `months` e [] explicit → returnează gol
    Anul precedent e restrâns la aceleași luni ca `year` pentru comparație
    corectă (ex. Ian–Apr year vs Ian–Apr year-1).

    Marca Privată apare ca "brand" separat (Brand.is_private_label=True);
    celelalte branduri sunt enumerate după flag, sortate DESC după vânzări.
    Categoriile și produsele sunt sortate DESC după vânzări la fiecare nivel.
    """
    groups = _SCOPE_GROUPS.get(scope.lower(), _GROUPS_ADP)
    sources = [s for g in groups for s in g]
    year_prev = year - 1

    if not sources:
        return {
            "scope": scope, "year": year,
            "last_update": None, "brands": [], "grand_sales": Decimal(0),
            "grand_qty": Decimal(0), "grand_sales_prev": Decimal(0),
            "grand_qty_prev": Decimal(0), "ytd_months": [], "selected_months": [],
        }

    # "Nimic selectat" explicit → niciun rezultat.
    if months is not None and len(months) == 0:
        return {
            "scope": scope, "year": year,
            "last_update": await _last_update(session, tenant_id, sources=sources),
            "brands": [], "grand_sales": Decimal(0), "grand_qty": Decimal(0),
            "grand_sales_prev": Decimal(0), "grand_qty_prev": Decimal(0),
            "ytd_months": [], "selected_months": [],
        }

    # Detectează lunile disponibile în anul curent (auto-YTD default).
    months_stmt = (
        select(RawSale.month)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year == year,
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
        )
        .distinct()
    )
    ytd_months = sorted({int(r.month) for r in (await session.execute(months_stmt)).all()})

    # Dacă userul a ales explicit → folosim intersecția (să nu cerem luni
    # fără date, dar să respectăm selecția când există).
    if months is not None:
        selected = sorted({m for m in months if 1 <= m <= 12})
    else:
        selected = ytd_months

    if not selected:
        return {
            "scope": scope, "year": year,
            "last_update": await _last_update(session, tenant_id, sources=sources),
            "brands": [], "grand_sales": Decimal(0), "grand_qty": Decimal(0),
            "grand_sales_prev": Decimal(0), "grand_qty_prev": Decimal(0),
            "ytd_months": ytd_months, "selected_months": [],
        }

    # Agregăm pentru ambii ani, restrânși la lunile selectate.
    sales_stmt = (
        select(
            RawSale.product_id,
            RawSale.year,
            func.coalesce(func.sum(RawSale.amount), 0).label("sales"),
            func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
        )
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year.in_([year_prev, year]),
            RawSale.month.in_(selected),
            func.upper(RawSale.channel) == "KA",
            ImportBatch.source.in_(sources),
            RawSale.product_id.is_not(None),
        )
        .group_by(RawSale.product_id, RawSale.year)
    )
    sales_rows = (await session.execute(sales_stmt)).all()
    if not sales_rows:
        return {
            "scope": scope, "year": year,
            "last_update": await _last_update(session, tenant_id, sources=sources),
            "brands": [], "grand_sales": Decimal(0), "grand_qty": Decimal(0),
            "grand_sales_prev": Decimal(0), "grand_qty_prev": Decimal(0),
            "ytd_months": ytd_months, "selected_months": selected,
        }

    # Construiește dict: product_id → (sales_curr, qty_curr, sales_prev, qty_prev)
    sales_map: dict[UUID, list[Decimal]] = {}
    for r in sales_rows:
        pid = r.product_id
        entry = sales_map.setdefault(pid, [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
        if int(r.year) == year:
            entry[0] += Decimal(r.sales or 0)
            entry[1] += Decimal(r.qty or 0)
        else:
            entry[2] += Decimal(r.sales or 0)
            entry[3] += Decimal(r.qty or 0)
    product_ids = list(sales_map.keys())

    # Hidratare metadata: produs + brand + categorie.
    meta_stmt = (
        select(
            Product.id,
            Product.code,
            Product.name,
            Product.brand_id,
            Product.category_id,
            Brand.name.label("brand_name"),
            Brand.is_private_label,
            ProductCategory.code.label("cat_code"),
            ProductCategory.label.label("cat_label"),
        )
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
        .where(Product.id.in_(product_ids))
    )
    meta_rows = (await session.execute(meta_stmt)).all()

    # Arbore: brand_key → cat_key → product list
    brand_buckets: dict[tuple, dict[str, Any]] = {}

    is_sika_scope = scope.lower() == "sika"

    for m in meta_rows:
        entry = sales_map.get(m.id)
        if entry is None:
            continue
        sales, qty, sales_prev, qty_prev = entry
        if sales == 0 and qty == 0 and sales_prev == 0 and qty_prev == 0:
            continue

        brand_key = (m.brand_id, m.brand_name or "— fără brand —",
                     bool(m.is_private_label))
        # Pentru scope=sika folosim Target Market-urile Sika (Building Finishing,
        # Sealing & Bonding, Waterproofing, Flooring, etc.) în loc de categoriile
        # Adeplast (MU/EPS/UMEDE/DIBLURI).
        if is_sika_scope:
            tm_label = _classify_sika_tm(m.name)
            cat_key = (None, tm_label, tm_label)
        else:
            cat_key = (m.category_id, m.cat_code or "",
                       m.cat_label or "— fără categorie —")

        bb = brand_buckets.setdefault(brand_key, {
            "brand_id": m.brand_id,
            "name": m.brand_name or "— fără brand —",
            "is_private_label": bool(m.is_private_label),
            "sales": Decimal(0), "qty": Decimal(0),
            "sales_prev": Decimal(0), "qty_prev": Decimal(0),
            "categories": {},
        })
        bb["sales"] += sales
        bb["qty"] += qty
        bb["sales_prev"] += sales_prev
        bb["qty_prev"] += qty_prev

        if is_sika_scope:
            cat_label = cat_key[2]
            cat_code = ""
            cat_cat_id = None
        else:
            cat_label = m.cat_label or "— fără categorie —"
            cat_code = m.cat_code or ""
            cat_cat_id = m.category_id

        cb = bb["categories"].setdefault(cat_key, {
            "category_id": cat_cat_id,
            "code": cat_code,
            "label": cat_label,
            "sales": Decimal(0), "qty": Decimal(0),
            "sales_prev": Decimal(0), "qty_prev": Decimal(0),
            "products": [],
        })
        cb["sales"] += sales
        cb["qty"] += qty
        cb["sales_prev"] += sales_prev
        cb["qty_prev"] += qty_prev
        cb["products"].append({
            "product_id": m.id,
            "code": m.code,
            "name": m.name,
            "sales": sales,
            "qty": qty,
            "sales_prev": sales_prev,
            "qty_prev": qty_prev,
            "avg_price": (sales / qty) if qty > 0 else None,
            "avg_price_prev": (sales_prev / qty_prev) if qty_prev > 0 else None,
        })

    # Sortări descrescătoare pe toate nivelurile.
    brands_out: list[dict[str, Any]] = []
    grand_sales = Decimal(0)
    grand_qty = Decimal(0)
    grand_sales_prev = Decimal(0)
    grand_qty_prev = Decimal(0)
    for bb in brand_buckets.values():
        cats_out: list[dict[str, Any]] = []
        for cb in bb["categories"].values():
            cb["products"].sort(key=lambda p: (-p["sales"], p["name"].lower()))
            cat_out: dict[str, Any] = {
                "category_id": cb["category_id"],
                "code": cb["code"],
                "label": cb["label"],
                "sales": cb["sales"],
                "qty": cb["qty"],
                "sales_prev": cb["sales_prev"],
                "qty_prev": cb["qty_prev"],
                "products": cb["products"],
                "subgroups": None,
            }
            if (cb["code"] or "").upper() == "EPS":
                cat_out["subgroups"] = _build_eps_subgroups(cb["products"])
            cats_out.append(cat_out)
        cats_out.sort(key=lambda c: (-c["sales"], c["label"].lower()))
        brands_out.append({
            "brand_id": bb["brand_id"],
            "name": bb["name"],
            "is_private_label": bb["is_private_label"],
            "sales": bb["sales"],
            "qty": bb["qty"],
            "sales_prev": bb["sales_prev"],
            "qty_prev": bb["qty_prev"],
            "categories": cats_out,
        })
        grand_sales += bb["sales"]
        grand_qty += bb["qty"]
        grand_sales_prev += bb["sales_prev"]
        grand_qty_prev += bb["qty_prev"]

    # Ordine branduri: non-private descending by sales, apoi private label
    # descending by sales (Marca Privata mereu după brandurile "normale").
    brands_out.sort(
        key=lambda b: (1 if b["is_private_label"] else 0, -b["sales"],
                       b["name"].lower()),
    )

    return {
        "scope": scope,
        "year": year,
        "last_update": await _last_update(session, tenant_id, sources=sources),
        "brands": brands_out,
        "grand_sales": grand_sales,
        "grand_qty": grand_qty,
        "grand_sales_prev": grand_sales_prev,
        "grand_qty_prev": grand_qty_prev,
        "ytd_months": ytd_months,
        "selected_months": selected,
    }
