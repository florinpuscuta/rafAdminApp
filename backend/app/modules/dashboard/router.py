"""
Modulul `dashboard` — read-only, fără tabele proprii. Orchestrează agregări
din `sales` (care deține raw_sales) + hidratare nume din `stores`/`agents`.
"""
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.agents import service as agents_service
from app.modules.auth.deps import get_current_tenant_id
from collections import defaultdict
from decimal import Decimal

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
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    # Rezolvă chain → listă store_ids (caching hint: pentru tenant mic ok)
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
    # default: compare cu anul anterior dacă clientul n-a trimis explicit nimic
    effective_compare = (
        compare_year
        if compare_year is not None
        else (effective_year - 1 if effective_year is not None else None)
    )
    if effective_compare == effective_year:
        effective_compare = None  # n-are sens să comparăm anul cu el însuși

    kpis_data = await sales_service.overview_totals(
        session,
        tenant_id,
        effective_year,
        month=month,
        store_id=store_id,
        agent_id=agent_id,
        product_id=product_id,
        store_ids_in=chain_store_ids,
        product_ids_in=cat_product_ids,
    )
    all_store_sums = await sales_service.sum_by_store(
        session,
        tenant_id,
        effective_year,
        limit=None,
        month=month,
        agent_id=agent_id,
        product_id=product_id,
        store_ids_in=chain_store_ids,
        product_ids_in=cat_product_ids,
    )
    store_rows = all_store_sums[:10]
    agent_rows = await sales_service.sum_by_agent(
        session,
        tenant_id,
        effective_year,
        month=month,
        store_id=store_id,
        product_id=product_id,
        store_ids_in=chain_store_ids,
        product_ids_in=cat_product_ids,
    )
    product_rows = await sales_service.sum_by_product(
        session,
        tenant_id,
        effective_year,
        month=month,
        store_id=store_id,
        agent_id=agent_id,
        store_ids_in=chain_store_ids,
        product_ids_in=cat_product_ids,
    )
    # Chart-ul lunar reflectă scope-ul selectat (dar nu e filtrat pe lună —
    # arată distribuția pe 12 luni pentru scope-ul respectiv)
    monthly_rows = (
        await sales_service.sum_by_month(
            session,
            tenant_id,
            effective_year,
            store_id=store_id,
            agent_id=agent_id,
            product_id=product_id,
            store_ids_in=chain_store_ids,
            product_ids_in=cat_product_ids,
        )
        if effective_year is not None
        else []
    )

    compare_kpis_data = None
    monthly_compare_rows: list[tuple[int, object, int]] = []
    if effective_compare is not None:
        compare_kpis_data = await sales_service.overview_totals(
            session,
            tenant_id,
            effective_compare,
            month=month,
            store_id=store_id,
            agent_id=agent_id,
            product_id=product_id,
            store_ids_in=chain_store_ids,
            product_ids_in=cat_product_ids,
        )
        monthly_compare_rows = await sales_service.sum_by_month(
            session,
            tenant_id,
            effective_compare,
            store_id=store_id,
            agent_id=agent_id,
            product_id=product_id,
            store_ids_in=chain_store_ids,
            product_ids_in=cat_product_ids,
        )

    # Hidratăm DOAR ID-urile din all_store_sums (acoperă și top_stores, și chain agg)
    all_store_ids = [sid for sid, _, _ in all_store_sums if sid is not None]
    agent_ids = [aid for aid, _, _ in agent_rows if aid is not None]
    product_ids = [pid for pid, _, _, _ in product_rows if pid is not None]
    stores_map = await stores_service.get_many(session, tenant_id, all_store_ids)
    agents_map = await agents_service.get_many(session, tenant_id, agent_ids)
    products_map = await products_service.get_many(session, tenant_id, product_ids)

    # Agregare per chain în Python (respectă boundaries: sales nu știe de chain,
    # stores nu știe de raw_sales; dashboard compune).
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
            chain=k,
            total_amount=chain_totals[k],
            row_count=chain_rows[k],
            store_count=len(chain_stores[k]),
        )
        for k in sorted(chain_totals.keys(), key=lambda c: chain_totals[c], reverse=True)
    ]

    top_stores = [
        TopStoreRow(
            store_id=sid,
            store_name=(stores_map[sid].name if sid and sid in stores_map else "Nemapate"),
            chain=(stores_map[sid].chain if sid and sid in stores_map else None),
            total_amount=total,
            row_count=count,
        )
        for sid, total, count in store_rows
    ]
    top_agents = [
        TopAgentRow(
            agent_id=aid,
            agent_name=(
                agents_map[aid].full_name if aid and aid in agents_map else "Nemapați"
            ),
            total_amount=total,
            row_count=count,
        )
        for aid, total, count in agent_rows
    ]
    top_products = [
        TopProductRow(
            product_id=pid,
            product_code=(products_map[pid].code if pid and pid in products_map else "Nemapate"),
            product_name=(products_map[pid].name if pid and pid in products_map else "—"),
            category=(products_map[pid].category if pid and pid in products_map else None),
            total_amount=total,
            total_quantity=qty,
            row_count=count,
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

    # Scope info pentru breadcrumb — hidratăm nume din maps deja fetch-uite
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
        year=effective_year,
        month=month,
        chain=chain,
        category=category,
        scope=scope,
        available_years=years,
        kpis=OverviewKPIs(**kpis_data),
        top_stores=top_stores,
        top_agents=top_agents,
        monthly_totals=monthly_totals,
        top_chains=top_chains,
        top_products=top_products,
        compare_year=effective_compare,
        compare_kpis=OverviewKPIs(**compare_kpis_data) if compare_kpis_data else None,
        monthly_totals_compare=monthly_totals_compare,
    )


# Cei 4 clienți KA — eticheta din UI → `client_original` din
# `store_agent_mappings` (sursa de adevăr pentru ierarhia client→magazine).
_KA_CLIENTS: dict[str, str] = {
    "Dedeman": "DEDEMAN SRL",
    "Altex": "ALTEX ROMANIA SRL",
    "Leroy Merlin": "LEROY MERLIN ROMANIA SRL",
    "Hornbach": "HORNBACH CENTRALA SRL",
}


# Aceeași convenție ca `analiza_magazin`: scope-ul firmei se traduce în
# filtru pe ImportBatch.source. "sikadp" = combinat (toate sursele).
_SCOPE_SOURCES: dict[str, list[str]] = {
    "adp": ["sales_xlsx"],
    "sika": ["sika_mtd_xlsx", "sika_xlsx"],
    "sikadp": ["sales_xlsx", "sika_mtd_xlsx", "sika_xlsx"],
}


@router.get("/top-stores-by-chain", response_model=TopStoresByChainResponse)
async def top_stores_by_chain(
    chain: str | None = Query(None),
    year: int | None = Query(None, ge=1900, le=2100),
    scope: str | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Ranking magazine pentru un client KA (Dedeman / Altex / Leroy / Hornbach).

    Sursa de adevăr e `store_agent_mappings`: `client_original` ne dă lista
    de magazine canonice (`store_id`) ale clientului. Vânzările se agregă
    pe acele `store_id` din `raw_sales`, filtrat pe scope-ul firmei.
    """
    from sqlalchemy import func, select
    from app.modules.mappings.models import StoreAgentMapping
    from app.modules.sales.models import ImportBatch, RawSale
    from app.modules.stores.models import Store

    available_chains = list(_KA_CLIENTS.keys())
    years = await sales_service.available_years(session, tenant_id)
    effective_year = year if year is not None else (years[0] if years else None)

    if not chain or chain not in _KA_CLIENTS:
        return TopStoresByChainResponse(
            chain=chain or "",
            year=effective_year,
            available_chains=available_chains,
            rows=[],
        )

    client_original = _KA_CLIENTS[chain]

    # 1) Magazinele canonice ale clientului (sursa: tabela de mapări).
    store_ids_q = select(StoreAgentMapping.store_id).where(
        StoreAgentMapping.tenant_id == tenant_id,
        StoreAgentMapping.client_original == client_original,
        StoreAgentMapping.store_id.is_not(None),
    ).distinct()
    store_ids = [sid for (sid,) in (await session.execute(store_ids_q)).all() if sid]

    if not store_ids:
        return TopStoresByChainResponse(
            chain=chain,
            year=effective_year,
            available_chains=available_chains,
            rows=[],
        )

    # 2) Agregare vânzări pe acele magazine, cu filtru scope (firmă).
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
    if effective_year is not None:
        stmt = stmt.where(RawSale.year == effective_year)

    sources = _SCOPE_SOURCES.get(scope or "", [])
    if sources:
        stmt = stmt.join(ImportBatch, ImportBatch.id == RawSale.batch_id).where(
            ImportBatch.source.in_(sources)
        )

    sales_rows = (await session.execute(stmt)).all()

    # 3) Hidratăm numele canonice (din Store).
    stores_map = await stores_service.get_many(session, tenant_id, store_ids)

    aggregated: list[dict] = []
    for sid, total, rcount, skus in sales_rows:
        store = stores_map.get(sid)
        aggregated.append({
            "store_id": sid,
            "store_name": store.name if store else str(sid),
            "total": Decimal(total or 0),
            "rows": int(rcount),
            "skus": int(skus),
        })

    if not aggregated:
        return TopStoresByChainResponse(
            chain=chain,
            year=effective_year,
            available_chains=available_chains,
            rows=[],
        )

    # 4) Rank-uri și scor combinat.
    by_value = sorted(aggregated, key=lambda r: r["total"], reverse=True)
    rank_value = {id(r): i + 1 for i, r in enumerate(by_value)}
    by_sku = sorted(aggregated, key=lambda r: r["skus"], reverse=True)
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
        out.append(
            StoreRankRow(
                store_id=r["store_id"],
                store_name=r["store_name"],
                chain=chain,
                total_amount=r["total"],
                row_count=r["rows"],
                distinct_products=r["skus"],
                rank_value=rv,
                rank_sku=rs,
                score_combined=round(0.5 * norm_v + 0.5 * norm_s, 2),
            )
        )
    out.sort(key=lambda r: r.total_amount, reverse=True)

    return TopStoresByChainResponse(
        chain=chain,
        year=effective_year,
        available_chains=available_chains,
        rows=out,
    )
