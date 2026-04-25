"""Calcul de marja pe perioada selectata.

Pe scope (adp / sika / sikadp), pentru intervalul (from_year, from_month) →
(to_year, to_month) inclusiv:

  - agregam raw_sales (sum amount, sum quantity) pe produs
  - lookup production_prices pentru cost (din modulul pret_productie)
  - calculam marja per produs: (avg_sale - cost) / avg_sale
  - grupam:
      ADP    → ProductCategory.label
      SIKA   → Target Market (via grupe_produse._classify_sika_tm)
      SIKADP → label combinat: "<TM>" pentru produsele Sika, "<Categorie>"
               pentru produsele Adeplast (un singur tabel, cu source tag)

Produsele fara pret de productie sunt excluse din KPI-uri si listate separat
pentru transparenta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analiza_magazin_dashboard.service import (
    _shift,
    SCOPE_SOURCES as _AMD_SCOPE_SOURCES,
)
from app.modules.pret_productie.models import ProductionPrice
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import RawSale
from app.modules.sales.models import ImportBatch


SCOPE_SOURCES: dict[str, list[str]] = {
    "adp": ["sales_xlsx"],
    "sika": ["sika_mtd_xlsx", "sika_xlsx"],
    "sikadp": ["sales_xlsx", "sika_mtd_xlsx", "sika_xlsx"],
}


# Priority groups pentru dedup — mirroring consolidat/_scope_sources.
# Per grup, sursele sunt iterate in ordine de prioritate; o pereche (an, luna)
# revendicata de o sursa de prioritate mai mare nu mai este numarata din cea
# mai mica (ex: sika_mtd_xlsx > sika_xlsx pentru lunile suprapuse).
SCOPE_GROUPS: dict[str, list[list[str]]] = {
    "adp": [["sales_xlsx"]],
    "sika": [["sika_mtd_xlsx", "sika_xlsx"]],
    "sikadp": [["sales_xlsx"], ["sika_mtd_xlsx", "sika_xlsx"]],
}

SCOPE_PP: dict[str, list[str]] = {
    # scope sales → ce scope de pret de productie consideram pentru cost.
    "adp": ["adp"],
    "sika": ["sika"],
    "sikadp": ["adp", "sika"],
}

ADP_SOURCE = "sales_xlsx"
SIKA_SOURCES = {"sika_mtd_xlsx", "sika_xlsx"}


@dataclass
class ProductRow:
    product_id: UUID
    product_code: str
    product_name: str
    group_label: str
    group_kind: str  # "category" | "tm"
    revenue: Decimal
    quantity: Decimal
    avg_sale: Decimal
    cost: Decimal | None
    profit: Decimal | None
    margin_pct: Decimal | None


@dataclass
class GroupRow:
    label: str
    kind: str  # "category" | "tm" | "private_label"
    key: str = ""  # category code | tm label | "marca_privata"
    revenue: Decimal = Decimal(0)
    quantity: Decimal = Decimal(0)
    cost_total: Decimal = Decimal(0)
    profit: Decimal = Decimal(0)
    margin_pct: Decimal = Decimal(0)
    discount_allocated: Decimal = Decimal(0)  # negativ
    profit_net: Decimal = Decimal(0)
    margin_pct_net: Decimal = Decimal(0)
    products: list[ProductRow] = field(default_factory=list)


@dataclass
class MissingCostRow:
    product_id: UUID
    product_code: str
    product_name: str
    revenue: Decimal
    quantity: Decimal


@dataclass
class MargineData:
    scope: str
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    revenue_period: Decimal
    revenue_covered: Decimal
    cost_total: Decimal
    profit_total: Decimal
    margin_pct: Decimal
    coverage_pct: Decimal
    # Suma negativelor (storno fara product_id) pentru perioada — discount-ul
    # retroactiv emis de KA. Distribuit pe grupe via discount_rules.
    discount_total: Decimal
    discount_allocated_total: Decimal
    profit_net_total: Decimal
    margin_pct_net: Decimal
    products_with_cost: int
    products_missing_cost: int
    groups: list[GroupRow]
    missing_cost: list[MissingCostRow]


def _period_pairs(
    from_year: int, from_month: int, to_year: int, to_month: int,
) -> list[tuple[int, int]]:
    """Lista (year, month) inclusiv intre cele doua puncte."""
    out: list[tuple[int, int]] = []
    y, m = from_year, from_month
    end = (to_year, to_month)
    # garda: daca from > to → returneaza []
    if (y, m) > end:
        return out
    while (y, m) <= end:
        out.append((y, m))
        y, m = _shift(y, m, 1)
    return out


async def _aggregate_sales(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    pairs: list[tuple[int, int]],
) -> list[dict]:
    """Returneaza per (product_id) — revenue, qty, flaguri sursa.

    Aplica:
      - filtru `channel='KA'` (case-insensitive ca in Consolidat)
      - dedup `sika_mtd_xlsx` > `sika_xlsx` pe lunile suprapuse, asigurand
        paritate cu Consolidat (Revenue trebuie sa coincida).
    """
    if not pairs:
        return []
    groups = SCOPE_GROUPS.get(scope, [])
    if not groups:
        return []

    pair_set = set(pairs)
    years = sorted({y for y, _ in pairs})
    months = sorted({m for _, m in pairs})

    agg: dict[UUID, dict] = {}

    for group in groups:
        claimed: set[tuple[int, int]] = set()
        for src in group:
            # 1) Identificam ce perechi (an, luna) are aceasta sursa, sa stim
            #    ce putem revendica fata de surse de prioritate mai inalta.
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(years),
                    RawSale.month.in_(months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            } & pair_set
            new_pairs = source_pairs - claimed
            if not new_pairs:
                continue

            new_years = sorted({y for (y, _m) in new_pairs})
            new_months = sorted({m for (_y, m) in new_pairs})
            stmt = (
                select(
                    RawSale.product_id,
                    RawSale.year,
                    RawSale.month,
                    RawSale.amount,
                    RawSale.quantity,
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.product_id.is_not(None),
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
            )
            res = await session.execute(stmt)
            for row in res:
                if (row.year, row.month) not in new_pairs:
                    continue
                e = agg.setdefault(row.product_id, {
                    "product_id": row.product_id,
                    "revenue": Decimal(0),
                    "quantity": Decimal(0),
                    "is_sika": False,
                    "is_adp": False,
                })
                if row.amount is not None:
                    e["revenue"] += Decimal(row.amount)
                if row.quantity is not None:
                    e["quantity"] += Decimal(row.quantity)
                if src == ADP_SOURCE:
                    e["is_adp"] = True
                elif src in SIKA_SOURCES:
                    e["is_sika"] = True

            claimed |= new_pairs

    return list(agg.values())


async def _total_period_revenue(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    pairs: list[tuple[int, int]],
) -> Decimal:
    """Suma `amount` pe perioada — match cu Consolidat: filtru KA + dedup
    intre sika_mtd_xlsx > sika_xlsx, FARA filtru pe product_id (include si
    randurile fara produs mapat — corectii/storno).
    """
    if not pairs:
        return Decimal(0)
    groups = SCOPE_GROUPS.get(scope, [])
    if not groups:
        return Decimal(0)

    pair_set = set(pairs)
    years = sorted({y for y, _ in pairs})
    months = sorted({m for _, m in pairs})

    total = Decimal(0)
    for group in groups:
        claimed: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(years),
                    RawSale.month.in_(months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            } & pair_set
            new_pairs = source_pairs - claimed
            if not new_pairs:
                continue
            new_years = sorted({y for (y, _m) in new_pairs})
            new_months = sorted({m for (_y, m) in new_pairs})
            sum_stmt = (
                select(
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .group_by(RawSale.year, RawSale.month)
            )
            for r in (await session.execute(sum_stmt)).all():
                if (int(r.year), int(r.month)) in new_pairs:
                    total += Decimal(r.amt or 0)
            claimed |= new_pairs
    return total


async def _unmapped_per_client(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    pairs: list[tuple[int, int]],
) -> dict[str, Decimal]:
    """Per client_chain (split_part client ' | '): suma amount-urilor cu
    product_id NULL — cota de storno/discount retroactiv. Aceleasi filtre
    KA + dedup ca in restul agregarilor.
    """
    if not pairs:
        return {}
    groups = SCOPE_GROUPS.get(scope, [])
    if not groups:
        return {}
    pair_set = set(pairs)
    years = sorted({y for y, _ in pairs})
    months = sorted({m for _, m in pairs})
    chain_expr = func.split_part(RawSale.client, " | ", 1).label("chain")

    out: dict[str, Decimal] = {}
    for group in groups:
        claimed: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(years),
                    RawSale.month.in_(months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            } & pair_set
            new_pairs = source_pairs - claimed
            if not new_pairs:
                continue
            new_years = sorted({y for (y, _m) in new_pairs})
            new_months = sorted({m for (_y, m) in new_pairs})
            sum_stmt = (
                select(
                    chain_expr,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.product_id.is_(None),
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .group_by(chain_expr, RawSale.year, RawSale.month)
            )
            for r in (await session.execute(sum_stmt)).all():
                if (int(r.year), int(r.month)) in new_pairs:
                    chain = (r.chain or "").strip()
                    if not chain:
                        continue
                    out[chain] = out.get(chain, Decimal(0)) + Decimal(r.amt or 0)
            claimed |= new_pairs
    return out


async def _revenue_per_client_product(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    pairs: list[tuple[int, int]],
    product_ids: list[UUID],
) -> dict[tuple[str, UUID], Decimal]:
    """{(client_chain, product_id): revenue} pentru produsele date.
    Aceleasi filtre KA + dedup ca _aggregate_sales.
    """
    if not pairs or not product_ids:
        return {}
    groups = SCOPE_GROUPS.get(scope, [])
    if not groups:
        return {}
    pair_set = set(pairs)
    years = sorted({y for y, _ in pairs})
    months = sorted({m for _, m in pairs})
    chain_expr = func.split_part(RawSale.client, " | ", 1).label("chain")

    out: dict[tuple[str, UUID], Decimal] = {}
    for group in groups:
        claimed: set[tuple[int, int]] = set()
        for src in group:
            pairs_stmt = (
                select(RawSale.year, RawSale.month)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.year.in_(years),
                    RawSale.month.in_(months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .distinct()
            )
            source_pairs = {
                (int(r.year), int(r.month))
                for r in (await session.execute(pairs_stmt)).all()
            } & pair_set
            new_pairs = source_pairs - claimed
            if not new_pairs:
                continue
            new_years = sorted({y for (y, _m) in new_pairs})
            new_months = sorted({m for (_y, m) in new_pairs})
            sum_stmt = (
                select(
                    chain_expr,
                    RawSale.product_id,
                    RawSale.year,
                    RawSale.month,
                    func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
                )
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    RawSale.product_id.in_(product_ids),
                    RawSale.year.in_(new_years),
                    RawSale.month.in_(new_months),
                    func.upper(RawSale.channel) == "KA",
                    ImportBatch.source == src,
                )
                .group_by(chain_expr, RawSale.product_id, RawSale.year, RawSale.month)
            )
            for r in (await session.execute(sum_stmt)).all():
                if (int(r.year), int(r.month)) in new_pairs:
                    chain = (r.chain or "").strip()
                    if not chain:
                        continue
                    key = (chain, r.product_id)
                    out[key] = out.get(key, Decimal(0)) + Decimal(r.amt or 0)
            claimed |= new_pairs
    return out


async def _fetch_products(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    product_ids: list[UUID],
) -> dict[UUID, dict]:
    if not product_ids:
        return {}
    from app.modules.brands.models import Brand
    res = await session.execute(
        select(
            Product.id,
            Product.code,
            Product.name,
            Product.category_id,
            ProductCategory.code.label("cat_code"),
            ProductCategory.label.label("cat_label"),
            Brand.is_private_label,
        )
        .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .where(Product.tenant_id == tenant_id, Product.id.in_(product_ids))
    )
    return {
        row.id: {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "category_id": row.category_id,
            "category_code": row.cat_code,
            "category_label": row.cat_label,
            "is_private_label": bool(row.is_private_label),
        }
        for row in res
    }


async def _fetch_costs(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    product_ids: list[UUID],
) -> dict[tuple[UUID, str], Decimal]:
    """Returneaza {(product_id, scope_pp): cost}.

    Pentru scope=sikadp, vom avea atat 'adp' cat si 'sika' dictate de
    apartenenta produsului la sursa (decisa la agregare). Aici returnam toate.
    """
    if not product_ids:
        return {}
    pp_scopes = SCOPE_PP[scope]
    res = await session.execute(
        select(
            ProductionPrice.product_id,
            ProductionPrice.scope,
            ProductionPrice.price,
        )
        .where(
            ProductionPrice.tenant_id == tenant_id,
            ProductionPrice.product_id.in_(product_ids),
            ProductionPrice.scope.in_(pp_scopes),
        )
    )
    return {(row.product_id, row.scope): Decimal(row.price) for row in res}


def _resolve_cost(
    *, scope: str, is_adp: bool, is_sika: bool,
    costs: dict[tuple[UUID, str], Decimal], pid: UUID,
) -> Decimal | None:
    """Determina costul aplicabil unui produs in functie de scope + sursa."""
    if scope == "adp":
        return costs.get((pid, "adp"))
    if scope == "sika":
        return costs.get((pid, "sika"))
    # sikadp — alegem dupa sursa primara (Sika daca exista in sika sources,
    # altfel Adeplast). Daca produsul a aparut in ambele, prioritizam Sika
    # (cazul rar) — ramane consistent cu meniul Sika.
    if is_sika:
        c = costs.get((pid, "sika"))
        if c is not None:
            return c
    if is_adp:
        c = costs.get((pid, "adp"))
        if c is not None:
            return c
    # fallback: ce gasim primul
    return costs.get((pid, "sika")) or costs.get((pid, "adp"))


def _group_for(
    *, scope: str, is_adp: bool, is_sika: bool,
    category_code: str | None, category_label: str | None,
    is_private_label: bool, product_name: str,
) -> tuple[str, str, str]:
    """Returneaza (label, kind, key) pentru gruparea produsului.

    Pentru ADP / SIKADP, Marca Privata e tratata ca un BLOC separat care la
    randul lui se sub-grupeaza pe categorii (kind='private_label', key incepe
    cu 'mp::'). Pentru calculul de eligibilitate la discount, orice grupa
    'private_label' se mapeaza la regula singleton 'marca_privata'.
    """
    from app.modules.grupe_produse.service import _classify_sika_tm

    if scope == "adp" or (scope == "sikadp" and not is_sika):
        cat = category_label or "Fara categorie"
        code = category_code or "_unknown"
        if is_private_label:
            return (f"MP — {cat}", "private_label", f"mp::{code}")
        return (cat, "category", code)
    # sika scope sau partea sika din sikadp
    tm = _classify_sika_tm(product_name)
    return (tm, "tm", tm)


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    if den == 0:
        return Decimal(0)
    return num / den


async def build_margine(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
) -> MargineData:
    pairs = _period_pairs(from_year, from_month, to_year, to_month)
    revenue_period = await _total_period_revenue(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    sales_rows = await _aggregate_sales(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    pids = [r["product_id"] for r in sales_rows]
    products = await _fetch_products(
        session, tenant_id=tenant_id, product_ids=pids,
    )
    costs = await _fetch_costs(
        session, tenant_id=tenant_id, scope=scope, product_ids=pids,
    )

    groups: dict[tuple[str, str], GroupRow] = {}
    missing: list[MissingCostRow] = []
    revenue_covered = Decimal(0)
    cost_total = Decimal(0)
    products_with_cost = 0
    products_missing_cost = 0

    for sr in sales_rows:
        pid = sr["product_id"]
        prod = products.get(pid)
        if prod is None:
            continue
        revenue = sr["revenue"]
        qty = sr["quantity"]
        if revenue <= 0 or qty <= 0:
            continue
        avg_sale = _safe_div(revenue, qty)
        cost = _resolve_cost(
            scope=scope, is_adp=sr["is_adp"], is_sika=sr["is_sika"],
            costs=costs, pid=pid,
        )
        if cost is None:
            products_missing_cost += 1
            missing.append(MissingCostRow(
                product_id=pid,
                product_code=prod["code"],
                product_name=prod["name"],
                revenue=revenue,
                quantity=qty,
            ))
            continue
        products_with_cost += 1
        cost_line = cost * qty
        profit_line = revenue - cost_line
        margin_pct = _safe_div(profit_line, revenue) * Decimal(100)

        label, kind, key = _group_for(
            scope=scope, is_adp=sr["is_adp"], is_sika=sr["is_sika"],
            category_code=prod["category_code"],
            category_label=prod["category_label"],
            is_private_label=prod["is_private_label"],
            product_name=prod["name"] or "",
        )
        g = groups.setdefault(
            (kind, key),
            GroupRow(label=label, kind=kind, key=key),
        )
        g.revenue += revenue
        g.quantity += qty
        g.cost_total += cost_line
        g.profit += profit_line
        g.products.append(ProductRow(
            product_id=pid,
            product_code=prod["code"],
            product_name=prod["name"],
            group_label=label,
            group_kind=kind,
            revenue=revenue,
            quantity=qty,
            avg_sale=avg_sale,
            cost=cost,
            profit=profit_line,
            margin_pct=margin_pct,
        ))

        revenue_covered += revenue
        cost_total += cost_line

    # Margin per group + sort
    for g in groups.values():
        g.margin_pct = _safe_div(g.profit, g.revenue) * Decimal(100)
        g.products.sort(key=lambda p: p.revenue, reverse=True)

    profit_total = revenue_covered - cost_total
    margin_pct_total = _safe_div(profit_total, revenue_covered) * Decimal(100)
    coverage_pct = _safe_div(revenue_covered, revenue_period) * Decimal(100)

    # ── Alocare discount (storno) pe grupe via discount_rules ──
    from app.modules.discount_rules.service import load_rules_dict

    unmapped_per_client = await _unmapped_per_client(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    discount_total = sum(unmapped_per_client.values(), Decimal(0))

    # Pid-urile produselor cu cost (covered) — singurele care primesc alocare.
    covered_pids = [
        p.product_id for g in groups.values() for p in g.products
    ]
    rev_per_cp = await _revenue_per_client_product(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
        product_ids=covered_pids,
    )

    # Map pid → (group_kind, group_key) reconstituit cu acelasi clasificator.
    pid_to_group: dict[UUID, tuple[str, str]] = {}
    for g in groups.values():
        for p in g.products:
            pid_to_group[p.product_id] = (g.kind, g.key)

    # Revenue per (client, group_kind, group_key) pentru alocare.
    rev_per_cg: dict[tuple[str, str, str], Decimal] = {}
    for (chain, pid), rev in rev_per_cp.items():
        kg = pid_to_group.get(pid)
        if kg is None:
            continue
        if rev <= 0:
            continue
        k = (chain, kg[0], kg[1])
        rev_per_cg[k] = rev_per_cg.get(k, Decimal(0)) + rev

    rules = await load_rules_dict(session, tenant_id, scope)

    def _applies(chain: str, kind: str, key: str) -> bool:
        # Sub-grupele Marca Privata (mp::EPS, mp::MU, ...) cad sub regula
        # singleton 'private_label/marca_privata' din matricea de reguli.
        if kind == "private_label":
            return rules.get((chain, "private_label", "marca_privata"), True)
        return rules.get((chain, kind, key), True)

    # Alocare per client → distribuie D_chain pe (group_kind, group_key).
    allocations: dict[tuple[str, str], Decimal] = {}
    for chain, total_d in unmapped_per_client.items():
        if total_d == 0:
            continue
        eligible_rev = sum(
            (rev for (c, k, ke), rev in rev_per_cg.items()
             if c == chain and _applies(c, k, ke)),
            Decimal(0),
        )
        if eligible_rev == 0:
            continue
        for (c, k, ke), rev in rev_per_cg.items():
            if c != chain or not _applies(c, k, ke):
                continue
            share = total_d * rev / eligible_rev  # negativ daca total_d e negativ
            allocations[(k, ke)] = allocations.get((k, ke), Decimal(0)) + share

    for g in groups.values():
        g.discount_allocated = allocations.get((g.kind, g.key), Decimal(0))
        g.profit_net = g.profit + g.discount_allocated  # discount negativ
        g.margin_pct_net = _safe_div(g.profit_net, g.revenue) * Decimal(100)

    discount_allocated_total = sum(
        (g.discount_allocated for g in groups.values()),
        Decimal(0),
    )
    profit_net_total = profit_total + discount_allocated_total
    margin_pct_net = _safe_div(profit_net_total, revenue_covered) * Decimal(100)

    sorted_groups = sorted(
        groups.values(), key=lambda x: x.revenue, reverse=True,
    )
    missing.sort(key=lambda x: x.revenue, reverse=True)

    return MargineData(
        scope=scope,
        from_year=from_year, from_month=from_month,
        to_year=to_year, to_month=to_month,
        revenue_period=revenue_period,
        revenue_covered=revenue_covered,
        cost_total=cost_total,
        profit_total=profit_total,
        margin_pct=margin_pct_total,
        coverage_pct=coverage_pct,
        discount_total=discount_total,
        discount_allocated_total=discount_allocated_total,
        profit_net_total=profit_net_total,
        margin_pct_net=margin_pct_net,
        products_with_cost=products_with_cost,
        products_missing_cost=products_missing_cost,
        groups=sorted_groups,
        missing_cost=missing,
    )
