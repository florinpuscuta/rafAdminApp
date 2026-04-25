"""
Modulul `dashboard` — read-only, fără tabele proprii. Orchestrează agregări
din `sales` (care deține raw_sales) + hidratare nume din `stores`/`agents`.
"""
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.agents import service as agents_service
from app.modules.auth.deps import get_current_org_ids

from app.modules.dashboard.schemas import (
    DashboardOverview,
    MonthTotalRow,
    OverviewKPIs,
    ScopeInfo,
    StoreRankRow,
    TopAgentRow,
    TopChainRow,
    TopProductRow,
    TopStoresByChainResponse,
    TopStoreRow,
)
from app.modules.products import service as products_service
from app.modules.sales import service as sales_service
from app.modules.stores import service as stores_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _overview_for_org(
    session: AsyncSession, tenant_id: UUID,
    *, year: int | None, compare_year: int | None, month: int | None,
    store_id: UUID | None, agent_id: UUID | None, product_id: UUID | None,
    chain: str | None, category: str | None,
) -> DashboardOverview:
    chain_store_ids: list[UUID] | None = None
    if chain:
        stores_in_chain = await stores_service.list_by_chain(session, tenant_id, chain)
        chain_store_ids = [s.id for s in stores_in_chain]

    cat_product_ids: list[UUID] | None = None
    if category:
        prods = await products_service.list_by_category(session, tenant_id, category)
        cat_product_ids = [p.id for p in prods]
    years = await sales_service.available_years(session, tenant_id)
    effective_year = year if year is not None else (years[0] if years else None)
    effective_compare = (
        compare_year
        if compare_year is not None
        else (effective_year - 1 if effective_year is not None else None)
    )
    if effective_compare == effective_year:
        effective_compare = None

    kpis_data = await sales_service.overview_totals(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, agent_id=agent_id, product_id=product_id,
        store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
    )
    all_store_sums = await sales_service.sum_by_store(
        session, tenant_id, effective_year, limit=None,
        month=month, agent_id=agent_id, product_id=product_id,
        store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
    )
    store_rows = all_store_sums[:10]
    agent_rows = await sales_service.sum_by_agent(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, product_id=product_id,
        store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
    )
    product_rows = await sales_service.sum_by_product(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, agent_id=agent_id,
        store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
    )
    monthly_rows = (
        await sales_service.sum_by_month(
            session, tenant_id, effective_year,
            store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
        )
        if effective_year is not None
        else []
    )

    compare_kpis_data = None
    monthly_compare_rows: list[tuple[int, object, int]] = []
    if effective_compare is not None:
        compare_kpis_data = await sales_service.overview_totals(
            session, tenant_id, effective_compare,
            month=month, store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
        )
        monthly_compare_rows = await sales_service.sum_by_month(
            session, tenant_id, effective_compare,
            store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids, product_ids_in=cat_product_ids,
        )

    all_store_ids = [sid for sid, _, _ in all_store_sums if sid is not None]
    agent_ids = [aid for aid, _, _ in agent_rows if aid is not None]
    product_ids = [pid for pid, _, _, _ in product_rows if pid is not None]
    stores_map = await stores_service.get_many(session, tenant_id, all_store_ids)
    agents_map = await agents_service.get_many(session, tenant_id, agent_ids)
    products_map = await products_service.get_many(session, tenant_id, product_ids)

    chain_totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    chain_rows: dict[str, int] = defaultdict(int)
    chain_stores: dict[str, set] = defaultdict(set)
    for sid, total, count in all_store_sums:
        if sid is None:
            key = "Nemapate"
        else:
            store = stores_map.get(sid)
            key = (store.chain if store and store.chain else "Fără lanț")
            chain_stores[key].add(sid)
        chain_totals[key] += total
        chain_rows[key] += count
    top_chains = [
        TopChainRow(
            chain=k, total_amount=chain_totals[k], row_count=chain_rows[k],
            store_count=len(chain_stores[k]),
        )
        for k in sorted(chain_totals.keys(), key=lambda c: chain_totals[c], reverse=True)
    ]

    top_stores = [
        TopStoreRow(
            store_id=sid,
            store_name=(stores_map[sid].name if sid and sid in stores_map else "Nemapate"),
            chain=(stores_map[sid].chain if sid and sid in stores_map else None),
            total_amount=total, row_count=count,
        )
        for sid, total, count in store_rows
    ]
    top_agents = [
        TopAgentRow(
            agent_id=aid,
            agent_name=(agents_map[aid].full_name if aid and aid in agents_map else "Nemapați"),
            total_amount=total, row_count=count,
        )
        for aid, total, count in agent_rows
    ]
    top_products = [
        TopProductRow(
            product_id=pid,
            product_code=(products_map[pid].code if pid and pid in products_map else "Nemapate"),
            product_name=(products_map[pid].name if pid and pid in products_map else "—"),
            category=(products_map[pid].category if pid and pid in products_map else None),
            total_amount=total, total_quantity=qty, row_count=count,
        )
        for pid, total, count, qty in product_rows
    ]
    monthly_totals = [
        MonthTotalRow(month=m, total_amount=total, row_count=count)
        for m, total, count in monthly_rows
    ]
    monthly_totals_compare = [
        MonthTotalRow(month=m, total_amount=total, row_count=count)
        for m, total, count in monthly_compare_rows
    ]

    scope: ScopeInfo | None = None
    if store_id or agent_id or product_id:
        scope = ScopeInfo()
        if store_id:
            s = stores_map.get(store_id) or (
                await stores_service.get_store(session, tenant_id, store_id)
            )
            scope.store_id = store_id
            scope.store_name = s.name if s else str(store_id)
        if agent_id:
            a = agents_map.get(agent_id) or (
                await agents_service.get_agent(session, tenant_id, agent_id)
            )
            scope.agent_id = agent_id
            scope.agent_name = a.full_name if a else str(agent_id)
        if product_id:
            p = products_map.get(product_id) or (
                await products_service.get_product(session, tenant_id, product_id)
            )
            scope.product_id = product_id
            scope.product_code = p.code if p else None
            scope.product_name = p.name if p else str(product_id)

    return DashboardOverview(
        year=effective_year, month=month, chain=chain, category=category,
        scope=scope, available_years=years,
        kpis=OverviewKPIs(**kpis_data),
        top_stores=top_stores, top_agents=top_agents,
        monthly_totals=monthly_totals, top_chains=top_chains,
        top_products=top_products,
        compare_year=effective_compare,
        compare_kpis=OverviewKPIs(**compare_kpis_data) if compare_kpis_data else None,
        monthly_totals_compare=monthly_totals_compare,
    )


def _sum_kpis(parts: list[OverviewKPIs]) -> OverviewKPIs:
    """Sum scalar KPI values across parts."""
    if not parts:
        return None  # type: ignore[return-value]
    fields = list(parts[0].model_fields.keys())
    out: dict = {}
    for f in fields:
        vals = [getattr(p, f) for p in parts]
        if not vals:
            out[f] = 0
            continue
        # Keep types consistent: Decimal stays Decimal; int stays int.
        first = vals[0]
        if isinstance(first, Decimal):
            out[f] = sum((v or Decimal(0) for v in vals), Decimal(0))
        elif isinstance(first, (int, float)):
            out[f] = sum((v or 0 for v in vals))
        else:
            out[f] = first
    return OverviewKPIs(**out)


def _merge_overview(parts: list[DashboardOverview]) -> DashboardOverview:
    first = parts[0]
    # available_years: union sorted desc
    years_union = sorted(
        {y for p in parts for y in (p.available_years or [])}, reverse=True,
    )

    # KPIs sumate
    kpis = _sum_kpis([p.kpis for p in parts]) if parts else first.kpis
    has_compare = any(p.compare_kpis is not None for p in parts)
    compare_kpis = (
        _sum_kpis([p.compare_kpis for p in parts if p.compare_kpis is not None])
        if has_compare else None
    )

    # Top stores: merge by name, sum total+row_count, top 10
    store_acc: dict[str, dict] = {}
    for p in parts:
        for s in p.top_stores:
            existing = store_acc.get(s.store_name)
            if existing is None:
                store_acc[s.store_name] = {
                    "store_id": s.store_id, "store_name": s.store_name,
                    "chain": s.chain, "total_amount": s.total_amount,
                    "row_count": s.row_count,
                }
            else:
                existing["total_amount"] += s.total_amount
                existing["row_count"] += s.row_count
    top_stores = sorted(
        [TopStoreRow(**r) for r in store_acc.values()],
        key=lambda x: x.total_amount, reverse=True,
    )[:10]

    # Top agents: merge by name
    agent_acc: dict[str, dict] = {}
    for p in parts:
        for a in p.top_agents:
            existing = agent_acc.get(a.agent_name)
            if existing is None:
                agent_acc[a.agent_name] = {
                    "agent_id": a.agent_id, "agent_name": a.agent_name,
                    "total_amount": a.total_amount, "row_count": a.row_count,
                }
            else:
                existing["total_amount"] += a.total_amount
                existing["row_count"] += a.row_count
    top_agents = sorted(
        [TopAgentRow(**r) for r in agent_acc.values()],
        key=lambda x: x.total_amount, reverse=True,
    )[:10]

    # Top chains: merge by chain string
    chain_acc: dict[str, dict] = {}
    for p in parts:
        for c in p.top_chains:
            existing = chain_acc.get(c.chain)
            if existing is None:
                chain_acc[c.chain] = {
                    "chain": c.chain, "total_amount": c.total_amount,
                    "row_count": c.row_count, "store_count": c.store_count,
                }
            else:
                existing["total_amount"] += c.total_amount
                existing["row_count"] += c.row_count
                existing["store_count"] += c.store_count
    top_chains = sorted(
        [TopChainRow(**r) for r in chain_acc.values()],
        key=lambda x: x.total_amount, reverse=True,
    )

    # Top products: merge by code (products unique cross-org → concat by code)
    prod_acc: dict[str, dict] = {}
    for p in parts:
        for pr in p.top_products:
            key = pr.product_code
            existing = prod_acc.get(key)
            if existing is None:
                prod_acc[key] = {
                    "product_id": pr.product_id, "product_code": pr.product_code,
                    "product_name": pr.product_name, "category": pr.category,
                    "total_amount": pr.total_amount,
                    "total_quantity": pr.total_quantity, "row_count": pr.row_count,
                }
            else:
                existing["total_amount"] += pr.total_amount
                existing["total_quantity"] += pr.total_quantity
                existing["row_count"] += pr.row_count
    top_products = sorted(
        [TopProductRow(**r) for r in prod_acc.values()],
        key=lambda x: x.total_amount, reverse=True,
    )[:10]

    # Monthly: sum per month
    def _merge_monthly(rows_per_part: list[list[MonthTotalRow]]) -> list[MonthTotalRow]:
        m_acc: dict[int, dict] = {}
        for rows in rows_per_part:
            for r in rows:
                e = m_acc.setdefault(r.month, {"month": r.month, "total_amount": Decimal(0), "row_count": 0})
                e["total_amount"] += r.total_amount
                e["row_count"] += r.row_count
        return sorted(
            [MonthTotalRow(**r) for r in m_acc.values()],
            key=lambda x: x.month,
        )

    monthly_totals = _merge_monthly([p.monthly_totals for p in parts])
    monthly_totals_compare = _merge_monthly([p.monthly_totals_compare for p in parts])

    # Scope: pick the first non-null
    scope = next((p.scope for p in parts if p.scope is not None), None)

    return DashboardOverview(
        year=first.year, month=first.month, chain=first.chain,
        category=first.category, scope=scope, available_years=years_union,
        kpis=kpis,
        top_stores=top_stores, top_agents=top_agents,
        monthly_totals=monthly_totals, top_chains=top_chains,
        top_products=top_products,
        compare_year=first.compare_year, compare_kpis=compare_kpis,
        monthly_totals_compare=monthly_totals_compare,
    )


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    year: int | None = Query(None, ge=1900, le=2100),
    compare_year: int | None = Query(None, ge=1900, le=2100, alias="compareYear"),
    month: int | None = Query(None, ge=1, le=12),
    store_id: UUID | None = Query(None, alias="storeId"),
    agent_id: UUID | None = Query(None, alias="agentId"),
    product_id: UUID | None = Query(None, alias="productId"),
    chain: str | None = Query(None),
    category: str | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    parts = []
    for tid in org_ids:
        parts.append(await _overview_for_org(
            session, tid,
            year=year, compare_year=compare_year, month=month,
            store_id=store_id, agent_id=agent_id, product_id=product_id,
            chain=chain, category=category,
        ))
    if len(parts) == 1:
        return parts[0]
    return _merge_overview(parts)


# Cei 4 clienți KA — eticheta din UI → `client_original` din
# `store_agent_mappings` (sursa de adevăr pentru ierarhia client→magazine).
_KA_CLIENTS: dict[str, str] = {
    "Dedeman": "DEDEMAN SRL",
    "Altex": "ALTEX ROMANIA SRL",
    "Leroy Merlin": "LEROY MERLIN ROMANIA SRL",
    "Hornbach": "HORNBACH CENTRALA SRL",
}


_SCOPE_SOURCES: dict[str, list[str]] = {
    "adp": ["sales_xlsx"],
    "sika": ["sika_mtd_xlsx", "sika_xlsx"],
    "sikadp": ["sales_xlsx", "sika_mtd_xlsx", "sika_xlsx"],
}


async def _top_stores_for_org(
    session: AsyncSession, tenant_id: UUID,
    *, chain: str, year: int | None, scope: str | None,
) -> list[StoreRankRow]:
    from sqlalchemy import func, select
    from app.modules.mappings.models import StoreAgentMapping
    from app.modules.sales.models import ImportBatch, RawSale

    client_original = _KA_CLIENTS[chain]
    store_ids_q = select(StoreAgentMapping.store_id).where(
        StoreAgentMapping.tenant_id == tenant_id,
        StoreAgentMapping.client_original == client_original,
        StoreAgentMapping.store_id.is_not(None),
    ).distinct()
    store_ids = [sid for (sid,) in (await session.execute(store_ids_q)).all() if sid]
    if not store_ids:
        return []

    stmt = (
        select(
            RawSale.store_id.label("sid"),
            func.coalesce(func.sum(RawSale.amount), 0).label("total"),
            func.count(RawSale.id).label("rows"),
            func.count(func.distinct(RawSale.product_id)).label("skus"),
        )
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id.in_(store_ids),
        )
        .group_by(RawSale.store_id)
    )
    if year is not None:
        stmt = stmt.where(RawSale.year == year)
    sources = _SCOPE_SOURCES.get(scope or "", [])
    if sources:
        stmt = stmt.join(ImportBatch, ImportBatch.id == RawSale.batch_id).where(
            ImportBatch.source.in_(sources)
        )
    sales_rows = (await session.execute(stmt)).all()
    stores_map = await stores_service.get_many(session, tenant_id, store_ids)

    out: list[StoreRankRow] = []
    for sid, total, rcount, skus in sales_rows:
        store = stores_map.get(sid)
        out.append(StoreRankRow(
            store_id=sid,
            store_name=store.name if store else str(sid),
            chain=chain,
            total_amount=Decimal(total or 0),
            row_count=int(rcount), distinct_products=int(skus),
            rank_value=0, rank_sku=0, score_combined=0.0,  # populated post-merge
        ))
    return out


@router.get("/top-stores-by-chain", response_model=TopStoresByChainResponse)
async def top_stores_by_chain(
    chain: str | None = Query(None),
    year: int | None = Query(None, ge=1900, le=2100),
    scope: str | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """
    Ranking magazine pentru un client KA (Dedeman / Altex / Leroy / Hornbach).
    """
    available_chains = list(_KA_CLIENTS.keys())
    # Resolve effective_year ca union din toate orgile
    years_union: set[int] = set()
    for tid in org_ids:
        ys = await sales_service.available_years(session, tid)
        years_union.update(ys)
    years = sorted(years_union, reverse=True)
    effective_year = year if year is not None else (years[0] if years else None)

    if not chain or chain not in _KA_CLIENTS:
        return TopStoresByChainResponse(
            chain=chain or "", year=effective_year,
            available_chains=available_chains, rows=[],
        )

    # Iteram per org si concatenam — apoi merge by name
    all_rows: list[StoreRankRow] = []
    for tid in org_ids:
        all_rows.extend(await _top_stores_for_org(
            session, tid, chain=chain, year=effective_year, scope=scope,
        ))

    # Merge by store name (acelasi store poate fi duplicat in 2 orgs)
    by_name: dict[str, dict] = {}
    for r in all_rows:
        existing = by_name.get(r.store_name)
        if existing is None:
            by_name[r.store_name] = {
                "store_id": r.store_id, "store_name": r.store_name,
                "chain": r.chain, "total_amount": r.total_amount,
                "row_count": r.row_count,
                "distinct_products": r.distinct_products,
            }
        else:
            existing["total_amount"] += r.total_amount
            existing["row_count"] += r.row_count
            existing["distinct_products"] += r.distinct_products

    aggregated = list(by_name.values())
    if not aggregated:
        return TopStoresByChainResponse(
            chain=chain, year=effective_year,
            available_chains=available_chains, rows=[],
        )

    by_value = sorted(aggregated, key=lambda r: r["total_amount"], reverse=True)
    rank_value = {id(r): i + 1 for i, r in enumerate(by_value)}
    by_sku = sorted(aggregated, key=lambda r: r["distinct_products"], reverse=True)
    rank_sku = {id(r): i + 1 for i, r in enumerate(by_sku)}
    n = len(aggregated)
    out: list[StoreRankRow] = []
    for r in aggregated:
        rv = rank_value[id(r)]
        rs = rank_sku[id(r)]
        if n > 1:
            norm_v = (n - rv) / (n - 1) * 100.0
            norm_s = (n - rs) / (n - 1) * 100.0
        else:
            norm_v = norm_s = 100.0
        out.append(StoreRankRow(
            store_id=r["store_id"], store_name=r["store_name"], chain=r["chain"],
            total_amount=r["total_amount"], row_count=r["row_count"],
            distinct_products=r["distinct_products"],
            rank_value=rv, rank_sku=rs,
            score_combined=round(0.5 * norm_v + 0.5 * norm_s, 2),
        ))
    out.sort(key=lambda r: r.total_amount, reverse=True)

    return TopStoresByChainResponse(
        chain=chain, year=effective_year,
        available_chains=available_chains, rows=out,
    )
