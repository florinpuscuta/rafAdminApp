from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from collections import defaultdict
from decimal import Decimal

from app.modules.auth.deps import get_current_org_ids
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
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

    async def _fetch(tid: UUID) -> dict:
        if scope == "adp":
            return await svc.get_for_adp(session, tid, year_curr=year_curr, month=month_val)
        if scope == "sika":
            return await svc.get_for_sika(session, tid, year_curr=year_curr, month=month_val)
        return await svc.get_for_sikadp(session, tid, year_curr=year_curr, month=month_val)

    parts = [await _fetch(tid) for tid in org_ids]
    merged = parts[0] if len(parts) == 1 else _merge_parts(parts, scope)

    if scope == "adp":
        return VzResponse(
            scope="adp",
            year_curr=merged["year_curr"], year_prev=merged["year_prev"],
            month=merged["month"], month_name=merged["month_name"],
            report_date=merged["report_date"], last_update=merged["last_update"],
            kpis=_kpis_to_model(merged["kpis"]),
            ind_processed=merged["ind_processed"],
            ind_missing=merged["ind_missing"],
            ind_processed_amount=merged["ind_processed_amount"],
            ind_missing_amount=merged["ind_missing_amount"],
            agents=_agents_to_models(merged["agents"]),
        )
    if scope == "sika":
        return VzResponse(
            scope="sika",
            year_curr=merged["year_curr"], year_prev=merged["year_prev"],
            month=merged["month"], month_name=merged["month_name"],
            report_date=merged["report_date"], last_update=merged["last_update"],
            kpis=_kpis_to_model(merged["kpis"]),
            agents=_agents_to_models(merged["agents"]),
        )
    return VzResponse(
        scope="sikadp",
        year_curr=merged["year_curr"], year_prev=merged["year_prev"],
        month=merged["month"], month_name=merged["month_name"],
        last_update=merged["last_update"],
        combined=VzCombinedBlock(
            kpis=_kpis_to_model(merged["combined"]["kpis"]),
            agents=_agents_to_models(merged["combined"]["agents"]),
        ),
        adeplast=VzScopeBlock(
            kpis=_kpis_to_model(merged["adeplast"]["kpis"]),
            report_date=merged["adeplast"]["report_date"],
            ind_processed=merged["adeplast"]["ind_processed"],
            ind_missing=merged["adeplast"]["ind_missing"],
            ind_processed_amount=merged["adeplast"]["ind_processed_amount"],
            ind_missing_amount=merged["adeplast"]["ind_missing_amount"],
        ),
        sika=VzScopeBlock(
            kpis=_kpis_to_model(merged["sika"]["kpis"]),
            report_date=merged["sika"]["report_date"],
        ),
    )


def _sum_kpis_dict(parts_kpis: list[dict]) -> dict:
    out = {
        "prev_sales": Decimal(0), "curr_sales": Decimal(0),
        "nelivrate": Decimal(0), "nefacturate": Decimal(0),
        "orders_total": Decimal(0), "exercitiu": Decimal(0), "gap": Decimal(0),
    }
    for k in parts_kpis:
        for f in out:
            v = k.get(f, Decimal(0)) or Decimal(0)
            out[f] += v
    return out


def _merge_agents(parts_agents: list[list[svc.AgentRow]]) -> list[svc.AgentRow]:
    """Agentii cu acelasi nume insumati cross-org, magazinele lor tot pe nume."""
    by_name: dict[str, svc.AgentRow] = {}
    for agents in parts_agents:
        for a in agents:
            existing = by_name.get(a.agent_name)
            if existing is None:
                by_name[a.agent_name] = a
                continue
            # Merge stores by name
            stores_by_name: dict[str, svc.StoreRow] = {
                sr.store_name: sr for sr in existing.stores.values()
            }
            for sr in a.stores.values():
                eg = stores_by_name.get(sr.store_name)
                if eg is None:
                    existing.stores[sr.store_id] = sr
                    stores_by_name[sr.store_name] = sr
                else:
                    eg.prev_sales += sr.prev_sales
                    eg.curr_sales += sr.curr_sales
                    eg.nelivrate += sr.nelivrate
                    eg.nefacturate += sr.nefacturate
                    eg.orders_total += sr.orders_total
                    eg.exercitiu += sr.exercitiu
            existing.stores_count = len(existing.stores)
    return sorted(by_name.values(), key=lambda a: a.totals()["curr_sales"], reverse=True)


def _max_dt(parts: list[dict], key: str):
    out = None
    for p in parts:
        v = p.get(key)
        if v is not None and (out is None or v > out):
            out = v
    return out


def _first_non_null(parts: list[dict], key: str):
    for p in parts:
        v = p.get(key)
        if v is not None:
            return v
    return None


def _merge_parts(parts: list[dict], scope: str) -> dict:
    first = parts[0]
    base = {
        "year_curr": first["year_curr"], "year_prev": first["year_prev"],
        "month": first["month"], "month_name": first["month_name"],
        "last_update": _max_dt(parts, "last_update"),
    }
    if scope == "adp":
        base["report_date"] = _first_non_null(parts, "report_date")
        base["kpis"] = _sum_kpis_dict([p["kpis"] for p in parts])
        base["ind_processed"] = sum((p.get("ind_processed", 0) for p in parts))
        base["ind_missing"] = sum((p.get("ind_missing", 0) for p in parts))
        base["ind_processed_amount"] = sum(
            (p.get("ind_processed_amount", Decimal(0)) for p in parts), Decimal(0),
        )
        base["ind_missing_amount"] = sum(
            (p.get("ind_missing_amount", Decimal(0)) for p in parts), Decimal(0),
        )
        base["agents"] = _merge_agents([p["agents"] for p in parts])
        return base
    if scope == "sika":
        base["report_date"] = _first_non_null(parts, "report_date")
        base["kpis"] = _sum_kpis_dict([p["kpis"] for p in parts])
        base["agents"] = _merge_agents([p["agents"] for p in parts])
        return base
    # sikadp — nested combined/adeplast/sika
    base["combined"] = {
        "kpis": _sum_kpis_dict([p["combined"]["kpis"] for p in parts]),
        "agents": _merge_agents([p["combined"]["agents"] for p in parts]),
    }
    base["adeplast"] = {
        "kpis": _sum_kpis_dict([p["adeplast"]["kpis"] for p in parts]),
        "report_date": _first_non_null([p["adeplast"] for p in parts], "report_date"),
        "ind_processed": sum((p["adeplast"].get("ind_processed", 0) for p in parts)),
        "ind_missing": sum((p["adeplast"].get("ind_missing", 0) for p in parts)),
        "ind_processed_amount": sum(
            (p["adeplast"].get("ind_processed_amount", Decimal(0)) for p in parts),
            Decimal(0),
        ),
        "ind_missing_amount": sum(
            (p["adeplast"].get("ind_missing_amount", Decimal(0)) for p in parts),
            Decimal(0),
        ),
    }
    base["sika"] = {
        "kpis": _sum_kpis_dict([p["sika"]["kpis"] for p in parts]),
        "report_date": _first_non_null([p["sika"] for p in parts], "report_date"),
    }
    return base
