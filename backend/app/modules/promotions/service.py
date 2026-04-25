"""Promotions — CRUD + simulare impact pe marja.

Simularea aplica reducerea pe revenue-ul perioadei istorice (baseline) folosit
ca proxy pentru ce ar fi vandut promotia. Volume neschimbate. Pentru raportul
final reconciliem cu vanzarile reale post-perioada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.period_math import shift_months
from app.modules.brands.models import Brand
from app.modules.grupe_produse.service import classify_sika_tm
from app.modules.margine import service as margine_svc
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.promotions.models import Promotion, PromotionTarget
from app.modules.sales.models import ImportBatch, RawSale


SCOPES = ("adp", "sika")
DISCOUNT_TYPES = ("pct", "override_price", "fixed_per_unit")
STATUSES = ("draft", "active", "archived")
TARGET_KINDS = ("product", "category", "tm", "private_label", "all")
BASELINE_KINDS = ("yoy", "mom")


_MONTH_NAMES_RO = [
    "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
    "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
]


# ── CRUD ───────────────────────────────────────────────────────────────────


async def search_products(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    q: str,
    limit: int = 25,
) -> list[dict]:
    """Cauta produse din scope dat care AU vanzari KA, dupa cod sau nume."""
    sources = ["sales_xlsx"] if scope == "adp" else ["sika_mtd_xlsx", "sika_xlsx"]
    pattern = f"%{q.strip()}%"
    stmt = (
        select(
            Product.id,
            Product.code,
            Product.name,
            ProductCategory.code.label("cat_code"),
            ProductCategory.label.label("cat_label"),
        )
        .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
        .where(
            Product.tenant_id == tenant_id,
            Product.id.in_(
                select(RawSale.product_id)
                .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
                .where(
                    RawSale.tenant_id == tenant_id,
                    ImportBatch.source.in_(sources),
                    func.upper(RawSale.channel) == "KA",
                    RawSale.product_id.is_not(None),
                )
            ),
        )
        .order_by(Product.name)
        .limit(limit)
    )
    if q.strip():
        stmt = stmt.where(
            (Product.code.ilike(pattern)) | (Product.name.ilike(pattern))
        )
    res = await session.execute(stmt)
    return [
        {
            "code": r.code,
            "name": r.name,
            "category_code": r.cat_code,
            "category_label": r.cat_label,
        }
        for r in res
    ]


async def list_groups(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
) -> list[dict]:
    """Pentru ADP: categorii cu vanzari KA + Marca Privata.
    Pentru SIKA: TM-urile distincte din vanzari KA.
    """
    if scope == "adp":
        cats_stmt = (
            select(ProductCategory.code, ProductCategory.label)
            .join(Product, Product.category_id == ProductCategory.id)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .join(RawSale, RawSale.product_id == Product.id)
            .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
            .where(
                Product.tenant_id == tenant_id,
                ImportBatch.source == "sales_xlsx",
                func.upper(RawSale.channel) == "KA",
                func.coalesce(Brand.is_private_label, False).is_(False),
            )
            .group_by(ProductCategory.code, ProductCategory.label, ProductCategory.sort_order)
            .order_by(ProductCategory.sort_order, ProductCategory.code)
        )
        out = [
            {"kind": "category", "key": r.code, "label": r.label}
            for r in (await session.execute(cats_stmt)).all()
        ]
        out.append({
            "kind": "private_label",
            "key": "marca_privata",
            "label": "Marca Privata",
        })
        return out
    # sika
    name_stmt = (
        select(Product.name)
        .join(RawSale, RawSale.product_id == Product.id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            Product.tenant_id == tenant_id,
            ImportBatch.source.in_(["sika_mtd_xlsx", "sika_xlsx"]),
            func.upper(RawSale.channel) == "KA",
        )
        .distinct()
    )
    seen: set[str] = set()
    for n in (await session.execute(name_stmt)).scalars():
        seen.add(classify_sika_tm(n or ""))
    return [
        {"kind": "tm", "key": tm, "label": tm}
        for tm in sorted(seen)
    ]


async def list_promotions(
    session: AsyncSession, tenant_id: UUID,
    *, scope: str | None = None, status: str | None = None,
) -> list[Promotion]:
    stmt = select(Promotion).where(Promotion.tenant_id == tenant_id)
    if scope:
        stmt = stmt.where(Promotion.scope == scope)
    if status:
        stmt = stmt.where(Promotion.status == status)
    stmt = stmt.order_by(
        Promotion.valid_from.desc(), Promotion.created_at.desc(),
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_promotion(
    session: AsyncSession, tenant_id: UUID, promo_id: UUID,
) -> Promotion | None:
    res = await session.execute(
        select(Promotion).where(
            Promotion.id == promo_id, Promotion.tenant_id == tenant_id,
        )
    )
    return res.scalar_one_or_none()


async def list_targets(
    session: AsyncSession, promo_id: UUID,
) -> list[PromotionTarget]:
    res = await session.execute(
        select(PromotionTarget)
        .where(PromotionTarget.promotion_id == promo_id)
        .order_by(PromotionTarget.kind, PromotionTarget.key)
    )
    return list(res.scalars().all())


async def create_promotion(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID | None,
    scope: str, name: str, status: str,
    discount_type: str, value: Decimal,
    valid_from: date, valid_to: date,
    client_filter: list[str] | None,
    notes: str | None,
    targets: list[dict],
) -> Promotion:
    promo = Promotion(
        tenant_id=tenant_id,
        scope=scope, name=name, status=status,
        discount_type=discount_type, value=value,
        valid_from=valid_from, valid_to=valid_to,
        client_filter=client_filter or None,
        notes=notes,
        created_by_user_id=user_id,
    )
    session.add(promo)
    await session.flush()
    for t in targets:
        session.add(PromotionTarget(
            promotion_id=promo.id, kind=t["kind"], key=t.get("key", ""),
        ))
    await session.commit()
    await session.refresh(promo)
    return promo


async def update_promotion(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    promo_id: UUID,
    fields: dict,
    targets: list[dict] | None,
) -> Promotion | None:
    promo = await get_promotion(session, tenant_id, promo_id)
    if promo is None:
        return None
    for k, v in fields.items():
        if hasattr(promo, k):
            setattr(promo, k, v)
    if targets is not None:
        await session.execute(
            delete(PromotionTarget).where(
                PromotionTarget.promotion_id == promo_id,
            )
        )
        for t in targets:
            session.add(PromotionTarget(
                promotion_id=promo_id, kind=t["kind"], key=t.get("key", ""),
            ))
    await session.commit()
    await session.refresh(promo)
    return promo


async def delete_promotion(
    session: AsyncSession, tenant_id: UUID, promo_id: UUID,
) -> bool:
    promo = await get_promotion(session, tenant_id, promo_id)
    if promo is None:
        return False
    await session.delete(promo)
    await session.commit()
    return True


# ── Simulare ───────────────────────────────────────────────────────────────


def _months_in_range(d_from: date, d_to: date) -> list[tuple[int, int]]:
    """Lista (year, month) inclusiv intre data start si data end."""
    out: list[tuple[int, int]] = []
    y, m = d_from.year, d_from.month
    end = (d_to.year, d_to.month)
    while (y, m) <= end:
        out.append((y, m))
        y, m = shift_months(y, m, 1)
    return out


def _baseline_pairs(
    promo_pairs: list[tuple[int, int]], kind: str,
) -> list[tuple[int, int]]:
    """YoY: shift -12 luni. MoM: aceeasi lungime imediat anterioara."""
    if kind == "yoy":
        return [shift_months(y, m, -12) for (y, m) in promo_pairs]
    if kind == "mom":
        n = len(promo_pairs)
        first_y, first_m = promo_pairs[0]
        prior_end = shift_months(first_y, first_m, -1)
        prior_start = shift_months(prior_end[0], prior_end[1], -(n - 1))
        out: list[tuple[int, int]] = []
        y, m = prior_start
        for _ in range(n):
            out.append((y, m))
            y, m = shift_months(y, m, 1)
        return out
    return promo_pairs


def _label_for_pairs(pairs: list[tuple[int, int]]) -> str:
    if not pairs:
        return ""
    if len(pairs) == 1:
        y, m = pairs[0]
        return f"{_MONTH_NAMES_RO[m]} {y}"
    y1, m1 = pairs[0]
    y2, m2 = pairs[-1]
    if y1 == y2:
        return f"{_MONTH_NAMES_RO[m1]}-{_MONTH_NAMES_RO[m2]} {y1}"
    return f"{_MONTH_NAMES_RO[m1]} {y1} - {_MONTH_NAMES_RO[m2]} {y2}"


@dataclass
class _ProductSummary:
    product_id: UUID
    revenue: Decimal
    quantity: Decimal
    is_adp: bool
    is_sika: bool


async def _aggregate_for_simulation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    pairs: list[tuple[int, int]],
    client_filter: list[str] | None,
) -> dict[UUID, _ProductSummary]:
    """Per-product revenue + qty pentru perioada data, scope KA, optional
    filtru pe client (chain). Aplica acelasi dedup ca margine.aggregate_sales,
    dar adauga filtrul client.
    """
    groups = margine_svc.SCOPE_GROUPS.get(scope, [])
    if not pairs or not groups:
        return {}
    pair_set = set(pairs)
    years = sorted({y for y, _ in pairs})
    months = sorted({m for _, m in pairs})

    chain_expr = func.split_part(RawSale.client, " | ", 1)
    client_clause = None
    if client_filter:
        client_clause = chain_expr.in_([c for c in client_filter if c])

    out: dict[UUID, _ProductSummary] = {}
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
            if client_clause is not None:
                pairs_stmt = pairs_stmt.where(client_clause)
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
            if client_clause is not None:
                stmt = stmt.where(client_clause)
            for r in (await session.execute(stmt)).all():
                if (r.year, r.month) not in new_pairs:
                    continue
                e = out.setdefault(r.product_id, _ProductSummary(
                    product_id=r.product_id,
                    revenue=Decimal(0), quantity=Decimal(0),
                    is_adp=False, is_sika=False,
                ))
                if r.amount is not None:
                    e.revenue += Decimal(r.amount)
                if r.quantity is not None:
                    e.quantity += Decimal(r.quantity)
                if src == margine_svc.ADP_SOURCE:
                    e.is_adp = True
                elif src in margine_svc.SIKA_SOURCES:
                    e.is_sika = True
            claimed |= new_pairs
    return out


def _matches_targets(
    *, targets: list[PromotionTarget],
    product_code: str, category_code: str | None,
    is_private_label: bool, product_name: str,
    scope: str,
) -> bool:
    """Verifica daca un produs intra in scope-ul promotiei."""
    if not targets:
        return False
    for t in targets:
        if t.kind == "all":
            return True
        if t.kind == "product" and t.key == product_code:
            return True
        if t.kind == "category" and category_code and t.key == category_code:
            return True
        if t.kind == "private_label" and is_private_label and t.key == "marca_privata":
            return True
        if t.kind == "tm":
            if scope in ("sika", "sikadp") and classify_sika_tm(product_name) == t.key:
                return True
    return False


def _apply_discount(
    *, discount_type: str, value: Decimal,
    revenue: Decimal, quantity: Decimal,
) -> Decimal:
    """Returneaza noul revenue dupa aplicarea discount-ului."""
    if quantity <= 0:
        return revenue
    if discount_type == "pct":
        # value e procent (0..100)
        factor = (Decimal(100) - value) / Decimal(100)
        if factor < 0:
            factor = Decimal(0)
        return revenue * factor
    if discount_type == "override_price":
        return quantity * value
    if discount_type == "fixed_per_unit":
        new_rev = revenue - quantity * value
        return new_rev if new_rev > 0 else Decimal(0)
    return revenue


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    if den == 0:
        return Decimal(0)
    return num / den


@dataclass
class SimGroupAcc:
    label: str
    kind: str
    key: str
    baseline_revenue: Decimal = Decimal(0)
    baseline_cost: Decimal = Decimal(0)
    scenario_revenue: Decimal = Decimal(0)
    scenario_cost: Decimal = Decimal(0)
    products_affected: int = 0


async def simulate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    promo_id: UUID,
    baseline_kind: str,
) -> dict | None:
    promo = await get_promotion(session, tenant_id, promo_id)
    if promo is None:
        return None
    targets = await list_targets(session, promo_id)

    promo_pairs = _months_in_range(promo.valid_from, promo.valid_to)
    baseline_pairs = _baseline_pairs(promo_pairs, baseline_kind)
    if not baseline_pairs:
        return None

    # Agregat pe produse pe baseline
    summaries = await _aggregate_for_simulation(
        session,
        tenant_id=tenant_id,
        scope=promo.scope,
        pairs=baseline_pairs,
        client_filter=promo.client_filter,
    )
    if not summaries:
        return _empty_response(promo, baseline_kind, baseline_pairs, promo_pairs)

    pids = list(summaries.keys())
    products = await margine_svc.fetch_products(
        session, tenant_id=tenant_id, product_ids=pids,
    )
    media_costs = await margine_svc.fetch_costs(
        session, tenant_id=tenant_id, scope=promo.scope, product_ids=pids,
    )

    groups: dict[tuple[str, str], SimGroupAcc] = {}
    products_in_scope = 0
    base_rev_total = Decimal(0)
    base_cost_total = Decimal(0)
    sim_rev_total = Decimal(0)
    sim_cost_total = Decimal(0)

    for pid, s in summaries.items():
        prod = products.get(pid)
        if prod is None:
            continue
        if not _matches_targets(
            targets=targets,
            product_code=prod["code"], category_code=prod["category_code"],
            is_private_label=prod["is_private_label"],
            product_name=prod["name"] or "",
            scope=promo.scope,
        ):
            continue
        if s.revenue <= 0 or s.quantity <= 0:
            continue
        cost_unit = margine_svc.resolve_cost(
            scope=promo.scope, is_adp=s.is_adp, is_sika=s.is_sika,
            costs=media_costs, pid=pid,
        )
        if cost_unit is None:
            continue
        cost_line = cost_unit * s.quantity
        scenario_rev = _apply_discount(
            discount_type=promo.discount_type, value=Decimal(promo.value),
            revenue=s.revenue, quantity=s.quantity,
        )

        label, kind, key = margine_svc.group_for(
            scope=promo.scope, is_adp=s.is_adp, is_sika=s.is_sika,
            category_code=prod["category_code"],
            category_label=prod["category_label"],
            is_private_label=prod["is_private_label"],
            product_name=prod["name"] or "",
        )
        g = groups.setdefault(
            (kind, key),
            SimGroupAcc(label=label, kind=kind, key=key),
        )
        g.baseline_revenue += s.revenue
        g.baseline_cost += cost_line
        g.scenario_revenue += scenario_rev
        g.scenario_cost += cost_line
        g.products_affected += 1

        products_in_scope += 1
        base_rev_total += s.revenue
        base_cost_total += cost_line
        sim_rev_total += scenario_rev
        sim_cost_total += cost_line

    base_profit_total = base_rev_total - base_cost_total
    sim_profit_total = sim_rev_total - sim_cost_total
    base_margin_total = _safe_div(base_profit_total, base_rev_total) * Decimal(100)
    sim_margin_total = _safe_div(sim_profit_total, sim_rev_total) * Decimal(100)

    out_groups = []
    for g in sorted(
        groups.values(), key=lambda x: x.baseline_revenue, reverse=True,
    ):
        b_profit = g.baseline_revenue - g.baseline_cost
        s_profit = g.scenario_revenue - g.scenario_cost
        b_margin = _safe_div(b_profit, g.baseline_revenue) * Decimal(100)
        s_margin = _safe_div(s_profit, g.scenario_revenue) * Decimal(100)
        out_groups.append({
            "label": g.label, "kind": g.kind, "key": g.key,
            "baseline_revenue": g.baseline_revenue,
            "baseline_cost": g.baseline_cost,
            "baseline_profit": b_profit,
            "baseline_margin_pct": b_margin,
            "scenario_revenue": g.scenario_revenue,
            "scenario_cost": g.scenario_cost,
            "scenario_profit": s_profit,
            "scenario_margin_pct": s_margin,
            "delta_revenue": g.scenario_revenue - g.baseline_revenue,
            "delta_profit": s_profit - b_profit,
            "delta_margin_pp": s_margin - b_margin,
            "products_affected": g.products_affected,
        })

    return {
        "promotion_id": promo.id,
        "baseline_kind": baseline_kind,
        "baseline_label": _label_for_pairs(baseline_pairs),
        "promo_label": _label_for_pairs(promo_pairs),
        "products_in_scope": products_in_scope,
        "baseline_revenue": base_rev_total,
        "baseline_cost": base_cost_total,
        "baseline_profit": base_profit_total,
        "baseline_margin_pct": base_margin_total,
        "scenario_revenue": sim_rev_total,
        "scenario_cost": sim_cost_total,
        "scenario_profit": sim_profit_total,
        "scenario_margin_pct": sim_margin_total,
        "delta_revenue": sim_rev_total - base_rev_total,
        "delta_profit": sim_profit_total - base_profit_total,
        "delta_margin_pp": sim_margin_total - base_margin_total,
        "groups": out_groups,
    }


def _empty_response(
    promo: Promotion,
    baseline_kind: str,
    baseline_pairs: list[tuple[int, int]],
    promo_pairs: list[tuple[int, int]],
) -> dict:
    z = Decimal(0)
    return {
        "promotion_id": promo.id,
        "baseline_kind": baseline_kind,
        "baseline_label": _label_for_pairs(baseline_pairs),
        "promo_label": _label_for_pairs(promo_pairs),
        "products_in_scope": 0,
        "baseline_revenue": z, "baseline_cost": z,
        "baseline_profit": z, "baseline_margin_pct": z,
        "scenario_revenue": z, "scenario_cost": z,
        "scenario_profit": z, "scenario_margin_pct": z,
        "delta_revenue": z, "delta_profit": z, "delta_margin_pp": z,
        "groups": [],
    }
