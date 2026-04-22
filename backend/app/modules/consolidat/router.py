from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.agents import service as agents_service
from app.modules.auth.deps import get_current_tenant_id
from app.modules.consolidat import service as service
from app.modules.consolidat.schemas import (
    ConsolidatAgentRow,
    ConsolidatAgentStoresResponse,
    ConsolidatKaResponse,
    ConsolidatStoreRow,
    ConsolidatTotals,
)
from app.modules.stores import service as stores_service

router = APIRouter(prefix="/api/consolidat", tags=["consolidat"])


_COMPANIES = {"adeplast", "sika", "sikadp"}


def _parse_months(value: str | None, *, default_to_ytd: bool) -> list[int]:
    """
    Parse CSV de luni. Dacă e gol + `default_to_ytd`, întoarce [1..month_curent].
    """
    if value:
        parsed: list[int] = []
        for p in value.split(","):
            p = p.strip()
            try:
                m = int(p)
            except ValueError:
                continue
            if 1 <= m <= 12:
                parsed.append(m)
        return sorted(set(parsed))
    if default_to_ytd:
        now = datetime.now(timezone.utc)
        return list(range(1, now.month + 1))
    return list(range(1, 13))


@router.get("/ka", response_model=ConsolidatKaResponse)
async def consolidat_ka(
    company: str = Query("adeplast"),
    y1: int | None = Query(None, ge=2000, le=2100),
    y2: int | None = Query(None, ge=2000, le=2100),
    months: str | None = Query(
        None,
        description="CSV luni 1..12. Gol = YTD până la luna curentă.",
    ),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    company = company.lower()
    if company not in _COMPANIES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_company", "message": "company trebuie adeplast|sika|sikadp"},
        )

    now = datetime.now(timezone.utc)
    if y2 is None:
        y2 = now.year
    if y1 is None:
        y1 = y2 - 1
    if y1 == y2:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_years", "message": "y1 și y2 trebuie să difere"},
        )

    months_list = _parse_months(months, default_to_ytd=True)

    totals_raw = await service.totals_for_company(
        session, tenant_id,
        company=company, y1=y1, y2=y2, months=months_list,
    )
    totals = ConsolidatTotals(
        sales_y1=totals_raw["sales_y1"],
        sales_y2=totals_raw["sales_y2"],
        diff=totals_raw["sales_y2"] - totals_raw["sales_y1"],
        pct=service.pct_change(totals_raw["sales_y1"], totals_raw["sales_y2"]),
    )

    agent_rows_raw = await service.by_agent(
        session, tenant_id,
        company=company, y1=y1, y2=y2, months=months_list,
    )
    # Hidrat nume agenți
    agent_ids = [r["agent_id"] for r in agent_rows_raw if r["agent_id"] is not None]
    agents_map: dict = {}
    if agent_ids:
        agents = await agents_service.get_many(session, tenant_id, agent_ids)
        agents_map = {aid: a.full_name for aid, a in agents.items()}

    agent_rows: list[ConsolidatAgentRow] = []
    for r in agent_rows_raw:
        diff = r["sales_y2"] - r["sales_y1"]
        agent_rows.append(
            ConsolidatAgentRow(
                agent_id=r["agent_id"],
                name=(
                    agents_map.get(r["agent_id"], "(necunoscut)")
                    if r["agent_id"]
                    else "(nemapat)"
                ),
                stores_count=r["stores_count"],
                sales_y1=r["sales_y1"],
                sales_y2=r["sales_y2"],
                diff=diff,
                pct=service.pct_change(r["sales_y1"], r["sales_y2"]),
            )
        )

    include_current_month = now.month in months_list and y2 == now.year

    return ConsolidatKaResponse(
        company=company,
        company_label=service._company_label(company),
        y1=y1,
        y2=y2,
        months=months_list,
        period_label=service.build_period_label(months_list),
        include_current_month=include_current_month,
        totals=totals,
        by_agent=agent_rows,
    )


@router.get(
    "/ka/agents/{agent_id}/stores",
    response_model=ConsolidatAgentStoresResponse,
)
async def consolidat_agent_stores(
    agent_id: str,
    company: str = Query("adeplast"),
    y1: int | None = Query(None, ge=2000, le=2100),
    y2: int | None = Query(None, ge=2000, le=2100),
    months: str | None = Query(None),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Defalcare magazine pentru un agent dat. `agent_id` = "none" pentru rânduri
    fără agent_id (nemapate).
    """
    company = company.lower()
    if company not in _COMPANIES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_company", "message": "company trebuie adeplast|sika|sikadp"},
        )

    agent_uuid: UUID | None
    if agent_id.lower() == "none":
        agent_uuid = None
    else:
        try:
            agent_uuid = UUID(agent_id)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "invalid_agent_id", "message": "agent_id invalid"},
            )

    now = datetime.now(timezone.utc)
    if y2 is None:
        y2 = now.year
    if y1 is None:
        y1 = y2 - 1

    months_list = _parse_months(months, default_to_ytd=True)

    rows = await service.by_store_per_agent(
        session, tenant_id,
        company=company, y1=y1, y2=y2, months=months_list,
        agent_id=agent_uuid,
    )

    store_ids = [r["store_id"] for r in rows if r["store_id"] is not None]
    stores_map: dict = {}
    if store_ids:
        stores_map = await stores_service.get_many(session, tenant_id, store_ids)

    out: list[ConsolidatStoreRow] = []
    for r in rows:
        store = stores_map.get(r["store_id"]) if r["store_id"] else None
        diff = r["sales_y2"] - r["sales_y1"]
        out.append(
            ConsolidatStoreRow(
                store_id=r["store_id"],
                name=store.name if store else "(nemapat)",
                chain=store.chain if store else None,
                city=store.city if store else None,
                sales_y1=r["sales_y1"],
                sales_y2=r["sales_y2"],
                diff=diff,
                pct=service.pct_change(r["sales_y1"], r["sales_y2"]),
            )
        )

    return ConsolidatAgentStoresResponse(
        agent_id=agent_uuid,
        company=company,
        y1=y1,
        y2=y2,
        months=months_list,
        stores=out,
    )
