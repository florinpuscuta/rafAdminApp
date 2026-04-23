"""
"Marca Privată" — breakdown vânzări KA pentru brandurile private label,
an curent vs an precedent.

Filtrul canonic (spre deosebire de legacy care folosea `brand='M_PRIVATA'`):
    raw_sales → products.brand_id → brands WHERE is_private_label = TRUE

Numai rândurile rezolvate la un Product cu brand canonic marcat ca private
label intră. Rândurile cu product_id NULL sau brand nemapat NU apar (se văd
separat în UI-ul de mapping).

Surse per scope (batch.source), grupate — dedup DOAR în interiorul unui grup:
  - adp → [["sales_xlsx"]]

(Sika/SIKADP nu sunt active — marca privată se aplică doar pe Adeplast.)

Output:
  - `months`: 12 celule lunare agregate (sales_y1, sales_y2, diff, pct)
  - `clients`: listă clienți cu sales/qty pe ambii ani (sortat desc. după y1)
  - `grand_totals`: totaluri pe an
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
from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
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

# Categoriile afișate în breakdown-ul pe rețea. Ordinea e fixă (UI o urmează).
CHAIN_CATEGORIES: list[tuple[str, str]] = [
    ("MU", "Mortare Uscate"),
    ("EPS", "EPS"),
    ("UMEDE", "Umede"),
]
CHAIN_CATEGORY_CODES: list[str] = [c for c, _ in CHAIN_CATEGORIES]

CHAIN_ORDER: list[str] = ["Dedeman", "Altex", "Leroy Merlin", "Hornbach", "Alte"]


def _extract_chain(raw: str | None) -> str:
    """Normalizează un `raw_sales.client` string la o rețea canonică.

    Aliniat cu `grupe_produse._extract_chain_from_client` și
    `mkt_facing._extract_chain` (aceeași listă Dedeman/Altex/Leroy/Hornbach).
    """
    if not raw:
        return "Alte"
    upper = raw.upper()
    if "DEDEMAN" in upper:
        return "Dedeman"
    if "ALTEX" in upper:
        return "Altex"
    if "LEROY" in upper or "MERLIN" in upper:
        return "Leroy Merlin"
    if "HORNBACH" in upper:
        return "Hornbach"
    return "Alte"


@dataclass
class MonthCell:
    month: int
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)


@dataclass
class CategoryCell:
    code: str
    label: str
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)


@dataclass
class ChainRow:
    chain: str
    sales_y1: Decimal = Decimal(0)
    sales_y2: Decimal = Decimal(0)
    categories: dict[str, CategoryCell] = field(default_factory=dict)

    @property
    def diff(self) -> Decimal:
        return self.sales_y2 - self.sales_y1

    @property
    def pct(self) -> Decimal | None:
        if self.sales_y1 == 0:
            return None
        return (self.diff / self.sales_y1) * Decimal(100)

    def cat(self, code: str, label: str) -> CategoryCell:
        return self.categories.setdefault(code, CategoryCell(code=code, label=label))


@dataclass
class MarcaPrivataData:
    scope: str
    year_curr: int
    year_prev: int
    last_update: datetime | None = None
    months: dict[int, MonthCell] = field(default_factory=dict)
    chains: list[ChainRow] = field(default_factory=list)

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
    """Lunile în `year` unde există măcar un rând private label KA."""
    sources = {s for g in batch_source_groups for s in g}
    if not sources:
        return set()
    stmt = (
        select(RawSale.month)
        .join(Product, Product.id == RawSale.product_id)
        .join(Brand, Brand.id == Product.brand_id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year == year,
            func.upper(RawSale.channel) == "KA",
            Brand.is_private_label.is_(True),
            ImportBatch.source.in_(sources),
        )
        .distinct()
    )
    return {int(r.month) for r in (await session.execute(stmt)).all()}


async def _raw_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Rânduri agregate private label KA pe (agent, store, client, year, month).

    În cadrul unui grup de surse, prioritizăm în ordinea listei — per
    (year, month) doar primul source contribuie. Grupurile se însumează.
    """
    year_prev = year_curr - 1
    out: dict[
        tuple[UUID | None, UUID | None, str | None, int, int],
        dict[str, Any],
    ] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(Product, Product.id == RawSale.product_id)
                .join(Brand, Brand.id == Product.brand_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    func.upper(RawSale.channel) == "KA",
                    Brand.is_private_label.is_(True),
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
                    RawSale.agent_id,
                    RawSale.store_id,
                    RawSale.client,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                    func.coalesce(func.sum(RawSale.quantity), 0).label("qty"),
                )
                .join(Product, Product.id == RawSale.product_id)
                .join(Brand, Brand.id == Product.brand_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    Brand.is_private_label.is_(True),
                    ImportBatch.source == src,
                )
                .group_by(
                    RawSale.agent_id, RawSale.store_id, RawSale.client,
                    RawSale.year, RawSale.month,
                )
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs:
                    continue
                key = (r.agent_id, r.store_id, r.client, int(r.year), int(r.month))
                row = out.setdefault(key, {
                    "agent_id": r.agent_id,
                    "store_id": r.store_id,
                    "client": r.client,
                    "year": int(r.year),
                    "month": int(r.month),
                    "amount": Decimal(0),
                    "quantity": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)
                row["quantity"] += Decimal(r.qty or 0)

            claimed_pairs |= new_pairs

    return list(out.values())


async def _chain_category_rows(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year_curr: int,
    batch_source_groups: list[list[str]],
    months_filter: set[int] | None,
) -> list[dict[str, Any]]:
    """Rânduri agregate private label KA pe (client, category_code, year).

    Filtrăm pe `ProductCategory.code IN ('MU','EPS','UMEDE')` — alte categorii
    (VARSACI etc.) nu intră în breakdown-ul pe rețea cerut de UI.
    Aceeași logică de dedup (primul source din grup câștigă perechea year,month).
    """
    year_prev = year_curr - 1
    out: dict[tuple[str | None, str, int], dict[str, Any]] = {}

    for group in batch_source_groups:
        claimed_pairs: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(Product, Product.id == RawSale.product_id)
                .join(Brand, Brand.id == Product.brand_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_([year_prev, year_curr]),
                    func.upper(RawSale.channel) == "KA",
                    Brand.is_private_label.is_(True),
                    ProductCategory.code.in_(CHAIN_CATEGORY_CODES),
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
                    RawSale.client,
                    ProductCategory.code.label("cat_code"),
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                )
                .join(Product, Product.id == RawSale.product_id)
                .join(Brand, Brand.id == Product.brand_id)
                .join(ProductCategory, ProductCategory.id == Product.category_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    Brand.is_private_label.is_(True),
                    ProductCategory.code.in_(CHAIN_CATEGORY_CODES),
                    ImportBatch.source == src,
                )
                .group_by(RawSale.client, ProductCategory.code, RawSale.year, RawSale.month)
            )
            result = await session.execute(stmt)
            for r in result.all():
                ym = (int(r.year), int(r.month))
                if ym not in new_pairs:
                    continue
                key = (r.client, str(r.cat_code), int(r.year))
                row = out.setdefault(key, {
                    "client": r.client,
                    "cat_code": str(r.cat_code),
                    "year": int(r.year),
                    "amount": Decimal(0),
                })
                row["amount"] += Decimal(r.amt or 0)

            claimed_pairs |= new_pairs

    return list(out.values())


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
) -> MarcaPrivataData:
    # Auto-YTD: restricționăm la lunile cu date în year_curr pentru comparație
    # pe perioade echivalente (ex. Ian-Apr vs Ian-Apr).
    if months_filter is None:
        months_filter = await _months_with_data(
            session, tenant_id,
            year=year_curr, batch_source_groups=batch_source_groups,
        )

    rows = await _raw_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        months_filter=months_filter,
    )

    # Rezolvare SAM pentru client canonic — în prezent doar consumăm
    # rezultatul (fără excluderi), dar păstrăm hook-ul pentru filtrări viitoare.
    client_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"]
        for r in rows
        if r["agent_id"] is None and r["store_id"] is not None
    }
    store_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    data = MarcaPrivataData(
        scope=scope,
        year_curr=year_curr,
        year_prev=year_curr - 1,
    )

    year_prev = year_curr - 1

    for r in rows:
        _resolved_agent, _resolved_store = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=client_map, store_map=store_map,
        )

        m = r["month"]
        cell = data.cell(m)
        if r["year"] == year_prev:
            cell.sales_y1 += r["amount"]
        elif r["year"] == year_curr:
            cell.sales_y2 += r["amount"]

    # Asigurăm 12 celule în output (chiar și 0).
    for m in range(1, 13):
        data.cell(m)

    # Agregare pe rețea (Dedeman/Altex/Leroy/Hornbach/Alte) × categorie
    # (MU/EPS/UMEDE). Se bazează pe produs.category_id → ProductCategory.code.
    cat_rows = await _chain_category_rows(
        session, tenant_id,
        year_curr=year_curr, batch_source_groups=batch_source_groups,
        months_filter=months_filter,
    )
    cat_labels = {code: label for code, label in CHAIN_CATEGORIES}
    by_chain: dict[str, ChainRow] = {}
    for r in cat_rows:
        chain = _extract_chain(r.get("client"))
        cr = by_chain.setdefault(chain, ChainRow(chain=chain))
        cc = cr.cat(r["cat_code"], cat_labels.get(r["cat_code"], r["cat_code"]))
        if r["year"] == year_prev:
            cr.sales_y1 += r["amount"]
            cc.sales_y1 += r["amount"]
        elif r["year"] == year_curr:
            cr.sales_y2 += r["amount"]
            cc.sales_y2 += r["amount"]

    # Ordonăm după CHAIN_ORDER (rețelele cunoscute primele), cu fallback pe
    # desc. sales_y1 pentru "Alte"/chains necunoscute.
    def _chain_sort_key(c: ChainRow) -> tuple[int, Decimal]:
        try:
            return (CHAIN_ORDER.index(c.chain), -c.sales_y1)
        except ValueError:
            return (len(CHAIN_ORDER), -c.sales_y1)

    data.chains = sorted(by_chain.values(), key=_chain_sort_key)

    data.last_update = await _last_update(
        session, tenant_id,
        sources=[s for g in batch_source_groups for s in g],
    )
    return data


async def get_for_adp(
    session: AsyncSession, tenant_id: UUID, *, year_curr: int,
    months_filter: set[int] | None = None,
) -> MarcaPrivataData:
    return await _build(
        session, tenant_id,
        scope="adp", year_curr=year_curr,
        batch_source_groups=_GROUPS_ADP,
        months_filter=months_filter,
    )
