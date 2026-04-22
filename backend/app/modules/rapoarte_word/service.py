"""Service pentru Raport Word.

Agregă datele de "overview" (KPI + top chains/stores/agents/products +
vânzări lunare CY vs PY) și le dă generatorului din
`app.modules.reports.generator`.

Logica e o copie fidelă a celei din `app.modules.reports.router.dashboard_report`
— diferența e că aici primim toate filtrările dintr-un payload pydantic,
nu din query params GET. Am extras-o ca să putem expune raportul și prin POST
(frontend-ul nou) fără să ne atingem de ruta veche.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents import service as agents_service
from app.modules.products import service as products_service
from app.modules.reports.generator import generate_dashboard_report
from app.modules.sales import service as sales_service
from app.modules.stores import service as stores_service
from app.modules.tenants import service as tenants_service


async def build_overview_dict(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None,
    month: int | None,
    compare_year: int | None,
    chain: str | None,
    store_id: UUID | None,
    agent_id: UUID | None,
    product_id: UUID | None,
) -> dict:
    years = await sales_service.available_years(session, tenant_id)
    effective_year = year if year is not None else (years[0] if years else None)
    effective_compare = (
        compare_year
        if compare_year is not None
        else (effective_year - 1 if effective_year is not None else None)
    )
    if effective_compare == effective_year:
        effective_compare = None

    chain_store_ids: list[UUID] | None = None
    if chain:
        stores_in_chain = await stores_service.list_by_chain(session, tenant_id, chain)
        chain_store_ids = [s.id for s in stores_in_chain]

    kpis = await sales_service.overview_totals(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, agent_id=agent_id, product_id=product_id,
        store_ids_in=chain_store_ids,
    )
    all_store_sums = await sales_service.sum_by_store(
        session, tenant_id, effective_year, limit=None,
        month=month, agent_id=agent_id, product_id=product_id,
        store_ids_in=chain_store_ids,
    )
    store_rows = all_store_sums[:10]
    agent_rows = await sales_service.sum_by_agent(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, product_id=product_id,
        store_ids_in=chain_store_ids,
    )
    product_rows = await sales_service.sum_by_product(
        session, tenant_id, effective_year,
        month=month, store_id=store_id, agent_id=agent_id,
        store_ids_in=chain_store_ids,
    )
    monthly_rows = (
        await sales_service.sum_by_month(
            session, tenant_id, effective_year,
            store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids,
        ) if effective_year is not None else []
    )
    monthly_compare_rows: list = []
    compare_kpis = None
    if effective_compare is not None:
        compare_kpis = await sales_service.overview_totals(
            session, tenant_id, effective_compare,
            month=month, store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids,
        )
        monthly_compare_rows = await sales_service.sum_by_month(
            session, tenant_id, effective_compare,
            store_id=store_id, agent_id=agent_id, product_id=product_id,
            store_ids_in=chain_store_ids,
        )

    sid_set = [sid for sid, _, _ in all_store_sums if sid is not None]
    aid_set = [aid for aid, _, _ in agent_rows if aid is not None]
    pid_set = [pid for pid, _, _, _ in product_rows if pid is not None]
    stores_map = await stores_service.get_many(session, tenant_id, sid_set)
    agents_map = await agents_service.get_many(session, tenant_id, aid_set)
    products_map = await products_service.get_many(session, tenant_id, pid_set)

    chain_totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    chain_rows: dict[str, int] = defaultdict(int)
    chain_stores: dict[str, set] = defaultdict(set)
    for sid, total, count in all_store_sums:
        if sid is None:
            key = "Nemapate"
        else:
            s = stores_map.get(sid)
            key = (s.chain if s and s.chain else "Fără lanț")
            chain_stores[key].add(sid)
        chain_totals[key] += total
        chain_rows[key] += count
    top_chains = [
        {"chain": k, "total_amount": chain_totals[k], "row_count": chain_rows[k],
         "store_count": len(chain_stores[k])}
        for k in sorted(chain_totals.keys(), key=lambda c: chain_totals[c], reverse=True)
    ]

    scope_dict = None
    if store_id or agent_id or product_id:
        scope_dict = {}
        if store_id:
            s = stores_map.get(store_id)
            scope_dict["store_name"] = s.name if s else str(store_id)
        if agent_id:
            a = agents_map.get(agent_id)
            scope_dict["agent_name"] = a.full_name if a else str(agent_id)
        if product_id:
            p = products_map.get(product_id)
            scope_dict["product_name"] = p.name if p else str(product_id)

    return {
        "year": effective_year,
        "month": month,
        "chain": chain,
        "scope": scope_dict,
        "compare_year": effective_compare,
        "kpis": kpis,
        "compare_kpis": compare_kpis,
        "monthly_totals": [
            {"month": m, "total_amount": t, "row_count": c} for m, t, c in monthly_rows
        ],
        "monthly_totals_compare": [
            {"month": m, "total_amount": t, "row_count": c} for m, t, c in monthly_compare_rows
        ],
        "top_stores": [
            {
                "store_name": (stores_map[sid].name if sid and sid in stores_map else "Nemapate"),
                "chain": (stores_map[sid].chain if sid and sid in stores_map else None),
                "total_amount": total,
            }
            for sid, total, _ in store_rows
        ],
        "top_agents": [
            {
                "agent_name": (agents_map[aid].full_name if aid and aid in agents_map else "Nemapați"),
                "total_amount": total,
            }
            for aid, total, _ in agent_rows
        ],
        "top_products": [
            {
                "product_code": (products_map[pid].code if pid and pid in products_map else "—"),
                "product_name": (products_map[pid].name if pid and pid in products_map else "—"),
                "total_amount": total,
            }
            for pid, total, _, _ in product_rows
        ],
        "top_chains": top_chains,
    }


async def generate_docx(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None,
    month: int | None,
    compare_year: int | None,
    chain: str | None,
    store_id: UUID | None,
    agent_id: UUID | None,
    product_id: UUID | None,
) -> tuple[bytes, str]:
    """Generează docx + filename. Filename-ul include anul/luna/lanțul."""
    overview = await build_overview_dict(
        session, tenant_id,
        year=year, month=month, compare_year=compare_year, chain=chain,
        store_id=store_id, agent_id=agent_id, product_id=product_id,
    )
    tenant = await tenants_service.get_by_id(session, tenant_id)
    tenant_name = tenant.name if tenant else "Organizația ta"

    docx_bytes = generate_dashboard_report(overview, tenant_name)

    fname_parts = ["raport"]
    if overview.get("year"):
        fname_parts.append(str(overview["year"]))
    if month:
        fname_parts.append(f"m{month:02d}")
    if chain:
        fname_parts.append(chain.lower().replace(" ", "-"))
    filename = "_".join(fname_parts) + ".docx"
    return docx_bytes, filename
