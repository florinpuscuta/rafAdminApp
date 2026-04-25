"""Analiza Marja Lunara — serie temporala marja per (luna, grupa).

Pentru fiecare (year, month) din intervalul cerut:
  - Agregam revenue per produs (KA + scope sources, dedup) — single-month window
  - Costul: prefer `ProductionPriceMonthly[Y, M]` → fallback la `ProductionPrice`
    (medie). Daca s-a folosit fallback, marcam luna respectiva cu un flag
    pentru disclaimer pe UI.
  - Grupare la fel ca Marja pe Perioada: categorii / Marca Privata / TM
  - Alocare discount aplicata pe luna (storno + reguli scope).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discount_rules.service import load_rules_dict
from app.modules.margine import service as margine_svc
from app.modules.pret_productie.models import ProductionPriceMonthly


@dataclass
class MLGroup:
    label: str
    kind: str  # 'category' | 'tm' | 'private_label'
    key: str
    revenue: Decimal = Decimal(0)
    quantity: Decimal = Decimal(0)
    cost_total: Decimal = Decimal(0)
    profit: Decimal = Decimal(0)
    margin_pct: Decimal = Decimal(0)
    discount_allocated: Decimal = Decimal(0)
    profit_net: Decimal = Decimal(0)
    margin_pct_net: Decimal = Decimal(0)


@dataclass
class MLMonth:
    year: int
    month: int
    revenue_period: Decimal = Decimal(0)
    revenue_covered: Decimal = Decimal(0)
    cost_total: Decimal = Decimal(0)
    profit_total: Decimal = Decimal(0)
    margin_pct: Decimal = Decimal(0)
    discount_total: Decimal = Decimal(0)
    discount_allocated_total: Decimal = Decimal(0)
    profit_net_total: Decimal = Decimal(0)
    margin_pct_net: Decimal = Decimal(0)
    has_monthly_snapshot: bool = False
    fallback_revenue_pct: Decimal = Decimal(0)
    products_with_cost: int = 0
    products_missing_cost: int = 0
    groups: list[MLGroup] = field(default_factory=list)


@dataclass
class MarjaLunaraData:
    scope: str
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    months: list[MLMonth] = field(default_factory=list)


async def _fetch_monthly_costs(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    year: int,
    month: int,
    product_ids: list[UUID],
) -> dict[UUID, Decimal]:
    if not product_ids:
        return {}
    pp_scopes = margine_svc.SCOPE_PP[scope]
    res = await session.execute(
        select(
            ProductionPriceMonthly.product_id,
            ProductionPriceMonthly.scope,
            ProductionPriceMonthly.price,
        ).where(
            ProductionPriceMonthly.tenant_id == tenant_id,
            ProductionPriceMonthly.scope.in_(pp_scopes),
            ProductionPriceMonthly.year == year,
            ProductionPriceMonthly.month == month,
            ProductionPriceMonthly.product_id.in_(product_ids),
        )
    )
    # Per pid alegem prima valoare gasita (in caz de scope multiple).
    out: dict[UUID, Decimal] = {}
    for row in res:
        out.setdefault(row.product_id, Decimal(row.price))
    return out


def _safe_div(num: Decimal, den: Decimal) -> Decimal:
    if den == 0:
        return Decimal(0)
    return num / den


async def _build_month(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    year: int,
    month: int,
    rules: dict[tuple[str, str, str], bool],
) -> MLMonth:
    pairs = [(year, month)]

    revenue_period = await margine_svc._total_period_revenue(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    sales_rows = await margine_svc._aggregate_sales(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    pids = [r["product_id"] for r in sales_rows]
    products = await margine_svc._fetch_products(
        session, tenant_id=tenant_id, product_ids=pids,
    )
    monthly_costs = await _fetch_monthly_costs(
        session, tenant_id=tenant_id, scope=scope, year=year, month=month,
        product_ids=pids,
    )
    media_costs = await margine_svc._fetch_costs(
        session, tenant_id=tenant_id, scope=scope, product_ids=pids,
    )

    groups: dict[tuple[str, str], MLGroup] = {}
    revenue_covered = Decimal(0)
    cost_total = Decimal(0)
    products_with_cost = 0
    products_missing_cost = 0
    fallback_revenue = Decimal(0)
    monthly_snapshot_used = False

    # group_key (str) → set of pids in that group (pentru alocare discount)
    pid_to_group: dict[UUID, tuple[str, str]] = {}

    for sr in sales_rows:
        pid = sr["product_id"]
        prod = products.get(pid)
        if prod is None:
            continue
        revenue = sr["revenue"]
        qty = sr["quantity"]
        if revenue <= 0 or qty <= 0:
            continue

        # Cost lookup: monthly first, fallback to media.
        cost: Decimal | None = monthly_costs.get(pid)
        used_fallback = False
        if cost is None:
            cost = margine_svc._resolve_cost(
                scope=scope, is_adp=sr["is_adp"], is_sika=sr["is_sika"],
                costs=media_costs, pid=pid,
            )
            used_fallback = cost is not None
        else:
            monthly_snapshot_used = True

        if cost is None:
            products_missing_cost += 1
            continue

        products_with_cost += 1
        cost_line = cost * qty
        profit_line = revenue - cost_line

        label, kind, key = margine_svc._group_for(
            scope=scope, is_adp=sr["is_adp"], is_sika=sr["is_sika"],
            category_code=prod["category_code"],
            category_label=prod["category_label"],
            is_private_label=prod["is_private_label"],
            product_name=prod["name"] or "",
        )
        g = groups.setdefault(
            (kind, key),
            MLGroup(label=label, kind=kind, key=key),
        )
        g.revenue += revenue
        g.quantity += qty
        g.cost_total += cost_line
        g.profit += profit_line
        revenue_covered += revenue
        cost_total += cost_line
        if used_fallback:
            fallback_revenue += revenue
        pid_to_group[pid] = (kind, key)

    # Marja bruta per grupa.
    for g in groups.values():
        g.margin_pct = _safe_div(g.profit, g.revenue) * Decimal(100)

    profit_total = revenue_covered - cost_total
    margin_pct_total = _safe_div(profit_total, revenue_covered) * Decimal(100)

    # ── Alocare discount pentru aceasta luna ──
    unmapped_per_client = await margine_svc._unmapped_per_client(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
    )
    discount_total = sum(unmapped_per_client.values(), Decimal(0))

    rev_per_cp = await margine_svc._revenue_per_client_product(
        session, tenant_id=tenant_id, scope=scope, pairs=pairs,
        product_ids=list(pid_to_group.keys()),
    )
    rev_per_cg: dict[tuple[str, str, str], Decimal] = {}
    for (chain, pid), rev in rev_per_cp.items():
        kg = pid_to_group.get(pid)
        if kg is None or rev <= 0:
            continue
        k = (chain, kg[0], kg[1])
        rev_per_cg[k] = rev_per_cg.get(k, Decimal(0)) + rev

    def _applies(chain: str, kind: str, key: str) -> bool:
        if kind == "private_label":
            return rules.get((chain, "private_label", "marca_privata"), True)
        return rules.get((chain, kind, key), True)

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
            share = total_d * rev / eligible_rev
            allocations[(k, ke)] = allocations.get((k, ke), Decimal(0)) + share

    for g in groups.values():
        g.discount_allocated = allocations.get((g.kind, g.key), Decimal(0))
        g.profit_net = g.profit + g.discount_allocated
        g.margin_pct_net = _safe_div(g.profit_net, g.revenue) * Decimal(100)

    discount_allocated_total = sum(
        (g.discount_allocated for g in groups.values()),
        Decimal(0),
    )
    profit_net_total = profit_total + discount_allocated_total
    margin_pct_net = _safe_div(profit_net_total, revenue_covered) * Decimal(100)

    fallback_pct = _safe_div(fallback_revenue, revenue_covered) * Decimal(100)
    sorted_groups = sorted(groups.values(), key=lambda x: x.revenue, reverse=True)

    return MLMonth(
        year=year, month=month,
        revenue_period=revenue_period,
        revenue_covered=revenue_covered,
        cost_total=cost_total,
        profit_total=profit_total,
        margin_pct=margin_pct_total,
        discount_total=discount_total,
        discount_allocated_total=discount_allocated_total,
        profit_net_total=profit_net_total,
        margin_pct_net=margin_pct_net,
        has_monthly_snapshot=monthly_snapshot_used,
        fallback_revenue_pct=fallback_pct,
        products_with_cost=products_with_cost,
        products_missing_cost=products_missing_cost,
        groups=sorted_groups,
    )


async def build_marja_lunara(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
) -> MarjaLunaraData:
    pairs = margine_svc._period_pairs(from_year, from_month, to_year, to_month)
    rules = await load_rules_dict(session, tenant_id, scope)
    months_out: list[MLMonth] = []
    for (y, m) in pairs:
        ml_month = await _build_month(
            session, tenant_id=tenant_id, scope=scope,
            year=y, month=m, rules=rules,
        )
        months_out.append(ml_month)
    return MarjaLunaraData(
        scope=scope,
        from_year=from_year, from_month=from_month,
        to_year=to_year, to_month=to_month,
        months=months_out,
    )
