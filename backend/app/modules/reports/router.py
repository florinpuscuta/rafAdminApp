"""
Reports router — generează exporturi Word din dashboard-ul curent.
Refolosește direct endpoint-ul dashboard.overview prin apel la service.
"""
from uuid import UUID

from fastapi import Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.agents import service as agents_service
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.products import service as products_service
from app.modules.reports.generator import generate_dashboard_report
from app.modules.sales import service as sales_service
from app.modules.stores import service as stores_service
from app.modules.tenants import service as tenants_service
from app.modules.users.models import User

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard.docx")
async def dashboard_report(
    year: int | None = Query(None, ge=1900, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    compare_year: int | None = Query(None, alias="compareYear"),
    chain: str | None = Query(None),
    store_id: UUID | None = Query(None, alias="storeId"),
    agent_id: UUID | None = Query(None, alias="agentId"),
    product_id: UUID | None = Query(None, alias="productId"),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    # Replicăm logica din dashboard.router.overview ca să producem
    # dict-ul "overview" așteptat de generator (formă internă cu snake_case).
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
    monthly_compare_rows = []
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

    # Hidratare pentru nume
    sid_set = [sid for sid, _, _ in all_store_sums if sid is not None]
    aid_set = [aid for aid, _, _ in agent_rows if aid is not None]
    pid_set = [pid for pid, _, _, _ in product_rows if pid is not None]
    stores_map = await stores_service.get_many(session, tenant_id, sid_set)
    agents_map = await agents_service.get_many(session, tenant_id, aid_set)
    products_map = await products_service.get_many(session, tenant_id, pid_set)

    # Agregare chain
    from collections import defaultdict
    from decimal import Decimal as D
    chain_totals: dict[str, D] = defaultdict(lambda: D(0))
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

    overview_dict = {
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

    tenant = await tenants_service.get_by_id(session, tenant_id)
    tenant_name = tenant.name if tenant else "Organizația ta"

    docx_bytes = generate_dashboard_report(overview_dict, tenant_name)

    from io import BytesIO
    buf = BytesIO(docx_bytes)
    fname_parts = ["raport"]
    if effective_year:
        fname_parts.append(str(effective_year))
    if month:
        fname_parts.append(f"m{month:02d}")
    if chain:
        fname_parts.append(chain.lower().replace(" ", "-"))
    filename = "_".join(fname_parts) + ".docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
