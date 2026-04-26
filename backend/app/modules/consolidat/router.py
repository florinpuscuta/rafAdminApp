from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.agents import service as agents_service
from app.modules.auth.deps import get_current_org_ids
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
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

    # Iteram per-org si sumam (paritate cu single-org views).
    # Pentru SIKADP (multi-org), agregam dupa NUMELE agentului si NUMELE
    # magazinului — store_id-urile sunt tenant-scoped, deci acelasi magazin
    # are UUID diferit in Adeplast vs Sika. Foloseste numele ca cheie de
    # deduplicare cross-org.
    total_y1 = Decimal(0)
    total_y2 = Decimal(0)
    by_name: dict[str, dict] = {}
    for tid in org_ids:
        totals_raw = await service.totals_for_company(
            session, tid, company=company, y1=y1, y2=y2, months=months_list,
        )
        total_y1 += totals_raw["sales_y1"]
        total_y2 += totals_raw["sales_y2"]

        agent_rows_raw = await service.by_agent(
            session, tid, company=company, y1=y1, y2=y2, months=months_list,
        )
        agent_ids = [r["agent_id"] for r in agent_rows_raw if r["agent_id"] is not None]
        agents = await agents_service.get_many(session, tid, agent_ids) if agent_ids else {}
        agents_map = {aid: a.full_name for aid, a in agents.items()}

        # Rezolvam toate store_id-urile la nume pentru aceasta orga (un singur query).
        all_store_ids: set[UUID] = set()
        for r in agent_rows_raw:
            all_store_ids.update(r["store_ids"])
        stores_map = (
            await stores_service.get_many(session, tid, list(all_store_ids))
            if all_store_ids else {}
        )

        for r in agent_rows_raw:
            name = agents_map.get(r["agent_id"], "(necunoscut)") if r["agent_id"] else "(nemapat)"
            # Convertim store_ids (tenant-scoped UUID) la nume (cross-org safe).
            store_names: set[str] = {
                stores_map[sid].name
                for sid in r["store_ids"]
                if sid in stores_map
            }
            existing = by_name.get(name)
            if existing is None:
                by_name[name] = {
                    "agent_id": r["agent_id"], "name": name,
                    "store_names": store_names,
                    "sales_y1": r["sales_y1"], "sales_y2": r["sales_y2"],
                }
            else:
                # Cross-org: union pe nume → magazinele comune se numara o singura data.
                existing["store_names"].update(store_names)
                existing["sales_y1"] += r["sales_y1"]
                existing["sales_y2"] += r["sales_y2"]

    totals = ConsolidatTotals(
        sales_y1=total_y1, sales_y2=total_y2,
        diff=total_y2 - total_y1,
        pct=service.pct_change(total_y1, total_y2),
    )
    agent_rows = sorted(
        [
            ConsolidatAgentRow(
                agent_id=r["agent_id"], name=r["name"],
                stores_count=len(r["store_names"]),
                sales_y1=r["sales_y1"], sales_y2=r["sales_y2"],
                diff=r["sales_y2"] - r["sales_y1"],
                pct=service.pct_change(r["sales_y1"], r["sales_y2"]),
            )
            for r in by_name.values()
        ],
        key=lambda x: x.sales_y2, reverse=True,
    )

    include_current_month = now.month in months_list and y2 == now.year
    return ConsolidatKaResponse(
        company=company,
        company_label=service._company_label(company),
        y1=y1, y2=y2, months=months_list,
        period_label=service.build_period_label(months_list),
        include_current_month=include_current_month,
        totals=totals, by_agent=agent_rows,
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """
    Defalcare magazine pentru un agent dat. `agent_id` = "none" pentru rânduri
    fără agent_id (nemapate). In consolidated mode, gasim agentul cu acelasi
    nume in fiecare orga si insumam.
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

    # In consolidated mode, agent_id e dintr-o singura orga. Rezolvam numele,
    # apoi cautam in fiecare orga agentul cu acelasi nume si sumam.
    agent_name: str | None = None
    if agent_uuid is not None:
        for tid in org_ids:
            a = (await agents_service.get_many(session, tid, [agent_uuid])).get(agent_uuid)
            if a is not None:
                agent_name = a.full_name
                break

    by_name: dict[str, dict] = {}
    for tid in org_ids:
        local_agent_id = agent_uuid
        if agent_name is not None and len(org_ids) > 1:
            # Cauta agentul cu acelasi nume in aceasta orga
            from sqlalchemy import select
            from app.modules.agents.models import Agent
            res = await session.execute(
                select(Agent).where(
                    Agent.tenant_id == tid, Agent.full_name == agent_name,
                )
            )
            local = res.scalar_one_or_none()
            local_agent_id = local.id if local else None
            if local_agent_id is None and agent_uuid is not None:
                continue  # niciun agent cu acest nume in aceasta orga

        rows = await service.by_store_per_agent(
            session, tid, company=company, y1=y1, y2=y2,
            months=months_list, agent_id=local_agent_id,
        )
        store_ids = [r["store_id"] for r in rows if r["store_id"] is not None]
        stores_map = (
            await stores_service.get_many(session, tid, store_ids)
            if store_ids else {}
        )
        for r in rows:
            store = stores_map.get(r["store_id"]) if r["store_id"] else None
            name = store.name if store else "(nemapat)"
            existing = by_name.get(name)
            if existing is None:
                by_name[name] = {
                    "store_id": r["store_id"], "name": name,
                    "chain": store.chain if store else None,
                    "city": store.city if store else None,
                    "sales_y1": r["sales_y1"], "sales_y2": r["sales_y2"],
                }
            else:
                existing["sales_y1"] += r["sales_y1"]
                existing["sales_y2"] += r["sales_y2"]

    out: list[ConsolidatStoreRow] = sorted(
        [
            ConsolidatStoreRow(
                store_id=r["store_id"], name=r["name"],
                chain=r["chain"], city=r["city"],
                sales_y1=r["sales_y1"], sales_y2=r["sales_y2"],
                diff=r["sales_y2"] - r["sales_y1"],
                pct=service.pct_change(r["sales_y1"], r["sales_y2"]),
            )
            for r in by_name.values()
        ],
        key=lambda x: x.sales_y2, reverse=True,
    )

    return ConsolidatAgentStoresResponse(
        agent_id=agent_uuid,
        company=company,
        y1=y1,
        y2=y2,
        months=months_list,
        stores=out,
    )
