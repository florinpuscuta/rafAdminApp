from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.vz_la_zi import service as svc
from app.modules.vz_la_zi.schemas import (
    VzAgentRow,
    VzCombinedBlock,
    VzKpis,
    VzResponse,
    VzScopeBlock,
    VzStoreRow,
)

router = APIRouter(prefix="/api/vz-la-zi", tags=["vz-la-zi"])

_SCOPES = {"adp", "sika", "sikadp"}


def _kpis_to_model(d: dict) -> VzKpis:
    return VzKpis(
        prev_sales=d["prev_sales"],
        curr_sales=d["curr_sales"],
        nelivrate=d["nelivrate"],
        nefacturate=d["nefacturate"],
        orders_total=d["orders_total"],
        exercitiu=d["exercitiu"],
        gap=d.get("gap", d["exercitiu"] - d["prev_sales"]),
    )


def _agents_to_models(agents: list[svc.AgentRow]) -> list[VzAgentRow]:
    out: list[VzAgentRow] = []
    for a in agents:
        t = a.totals()
        stores = [
            VzStoreRow(
                store_id=sr.store_id,
                store_name=sr.store_name,
                prev_sales=sr.prev_sales,
                curr_sales=sr.curr_sales,
                nelivrate=sr.nelivrate,
                nefacturate=sr.nefacturate,
                orders_total=sr.orders_total,
                exercitiu=sr.exercitiu,
            )
            for sr in a.stores.values()
        ]
        out.append(
            VzAgentRow(
                agent_id=a.agent_id,
                agent_name=a.agent_name,
                stores_count=a.stores_count,
                prev_sales=t["prev_sales"],
                curr_sales=t["curr_sales"],
                nelivrate=t["nelivrate"],
                nefacturate=t["nefacturate"],
                orders_total=t["orders_total"],
                exercitiu=t["exercitiu"],
                stores=stores,
            )
        )
    return out


@router.get("", response_model=VzResponse)
async def get_vz_la_zi(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, alias="year", ge=2000, le=2100),
    month: int | None = Query(None, ge=1, le=12),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    scope = scope.lower()
    if scope not in _SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_scope", "message": "scope trebuie adp|sika|sikadp"},
        )

    now = datetime.now(timezone.utc)
    year_curr = year or now.year
    month_val = month or now.month

    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr, month=month_val)
        return VzResponse(
            scope="adp",
            year_curr=data["year_curr"],
            year_prev=data["year_prev"],
            month=data["month"],
            month_name=data["month_name"],
            report_date=data["report_date"],
            last_update=data["last_update"],
            kpis=_kpis_to_model(data["kpis"]),
            ind_processed=data["ind_processed"],
            ind_missing=data["ind_missing"],
            ind_processed_amount=data["ind_processed_amount"],
            ind_missing_amount=data["ind_missing_amount"],
            agents=_agents_to_models(data["agents"]),
        )

    if scope == "sika":
        data = await svc.get_for_sika(session, tenant_id, year_curr=year_curr, month=month_val)
        return VzResponse(
            scope="sika",
            year_curr=data["year_curr"],
            year_prev=data["year_prev"],
            month=data["month"],
            month_name=data["month_name"],
            report_date=data["report_date"],
            last_update=data["last_update"],
            kpis=_kpis_to_model(data["kpis"]),
            agents=_agents_to_models(data["agents"]),
        )

    # sikadp
    data = await svc.get_for_sikadp(session, tenant_id, year_curr=year_curr, month=month_val)
    return VzResponse(
        scope="sikadp",
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        month=data["month"],
        month_name=data["month_name"],
        last_update=data["last_update"],
        combined=VzCombinedBlock(
            kpis=_kpis_to_model(data["combined"]["kpis"]),
            agents=_agents_to_models(data["combined"]["agents"]),
        ),
        adeplast=VzScopeBlock(
            kpis=_kpis_to_model(data["adeplast"]["kpis"]),
            report_date=data["adeplast"]["report_date"],
            ind_processed=data["adeplast"]["ind_processed"],
            ind_missing=data["adeplast"]["ind_missing"],
            ind_processed_amount=data["adeplast"]["ind_processed_amount"],
            ind_missing_amount=data["adeplast"]["ind_missing_amount"],
        ),
        sika=VzScopeBlock(
            kpis=_kpis_to_model(data["sika"]["kpis"]),
            report_date=data["sika"]["report_date"],
        ),
    )
