from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_tenant_id
from app.modules.evaluare_agenti import service as svc
from app.modules.evaluare_agenti.schemas import (
    AgentCompList,
    AgentCompRow,
    AgentCompUpsert,
    MatrixResponse,
    MatrixRow,
    MonthInputList,
    MonthInputRow,
    MonthInputUpsert,
    RaionBonusCreate,
    RaionBonusList,
    RaionBonusRow,
    RaionBonusUpdate,
    ZonaAgentDetail,
    ZonaAgentSummary,
    ZonaAgentsResponse,
    ZonaBonusUpsert,
    ZonaStoreRow,
)

router = APIRouter(prefix="/api/evaluare-agenti", tags=["evaluare-agenti"])


def _validate_month(month: int) -> int:
    if not 1 <= month <= 12:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "month trebuie între 1 și 12"},
        )
    return month


def _validate_year(year: int) -> int:
    if not 2000 <= year <= 2100:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_year", "message": "year invalid"},
        )
    return year


# ───────────────── Pachet Salarial ─────────────────

@router.get("/compensation", response_model=AgentCompList)
async def list_compensation(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    pairs = await svc.list_compensation(session, tenant_id)
    rows = [
        AgentCompRow(
            agent_id=agent.id,
            agent_name=agent.full_name,
            salariu_fix=(comp.salariu_fix if comp else 0),
            note=(comp.note if comp else None),
            updated_at=(comp.updated_at if comp else None),
        )
        for agent, comp in pairs
    ]
    return AgentCompList(rows=rows)


@router.put("/compensation", response_model=AgentCompRow)
async def upsert_compensation(
    payload: AgentCompUpsert,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    comp = await svc.upsert_compensation(
        session,
        tenant_id=tenant_id,
        agent_id=payload.agent_id,
        salariu_fix=payload.salariu_fix,
        note=payload.note,
    )
    await session.commit()
    from app.modules.agents import service as agents_service
    agent = await agents_service.get_agent(session, tenant_id, payload.agent_id)
    return AgentCompRow(
        agent_id=comp.agent_id,
        agent_name=agent.full_name if agent else "",
        salariu_fix=comp.salariu_fix,
        note=comp.note,
        updated_at=comp.updated_at,
    )


# ───────────────── Input Lunar ─────────────────

@router.get("/month-inputs", response_model=MonthInputList)
async def list_month_inputs(
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows_data = await svc.list_month_inputs(session, tenant_id, year=y, month=m)
    return MonthInputList(
        year=y,
        month=m,
        rows=[MonthInputRow(year=y, month=m, **r) for r in rows_data],
    )


@router.put("/month-inputs", response_model=MonthInputRow)
async def upsert_month_input(
    payload: MonthInputUpsert,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(payload.year)
    m = _validate_month(payload.month)
    await svc.upsert_month_input(
        session,
        tenant_id=tenant_id,
        agent_id=payload.agent_id,
        year=y,
        month=m,
        cost_combustibil=payload.cost_combustibil,
        cost_revizii=payload.cost_revizii,
        alte_costuri=payload.alte_costuri,
        note=payload.note,
    )
    await session.commit()
    rows_data = await svc.list_month_inputs(session, tenant_id, year=y, month=m)
    match = next((r for r in rows_data if r["agent_id"] == payload.agent_id), None)
    if match is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent inexistent"},
        )
    return MonthInputRow(year=y, month=m, **match)


# ───────────────── Bonusări Oameni Raion ─────────────────

@router.get("/raion-bonus", response_model=RaionBonusList)
async def list_raion_bonus(
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows_data = await svc.list_raion_bonus(session, tenant_id, year=y, month=m)
    total = sum((r["suma"] for r in rows_data), Decimal("0"))
    return RaionBonusList(
        year=y,
        month=m,
        rows=[RaionBonusRow(**r) for r in rows_data],
        total=total,
    )


@router.post("/raion-bonus", response_model=RaionBonusRow, status_code=status.HTTP_201_CREATED)
async def create_raion_bonus(
    payload: RaionBonusCreate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(payload.year)
    m = _validate_month(payload.month)
    row = await svc.create_raion_bonus(
        session,
        tenant_id=tenant_id,
        store_id=payload.store_id,
        year=y,
        month=m,
        contact_name=payload.contact_name,
        suma=payload.suma,
        note=payload.note,
    )
    await session.commit()
    rows_data = await svc.list_raion_bonus(session, tenant_id, year=y, month=m)
    match = next((r for r in rows_data if r["id"] == row.id), None)
    assert match is not None
    return RaionBonusRow(**match)


@router.put("/raion-bonus/{id_}", response_model=RaionBonusRow)
async def update_raion_bonus(
    id_: UUID,
    payload: RaionBonusUpdate,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    row = await svc.update_raion_bonus(
        session,
        tenant_id=tenant_id,
        id_=id_,
        contact_name=payload.contact_name,
        suma=payload.suma,
        note=payload.note,
    )
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Bonus inexistent"},
        )
    await session.commit()
    rows_data = await svc.list_raion_bonus(
        session, tenant_id, year=row.year, month=row.month,
    )
    match = next((r for r in rows_data if r["id"] == row.id), None)
    assert match is not None
    return RaionBonusRow(**match)


@router.delete("/raion-bonus/{id_}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_raion_bonus(
    id_: UUID,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    ok = await svc.delete_raion_bonus(session, tenant_id=tenant_id, id_=id_)
    if not ok:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Bonus inexistent"},
        )
    await session.commit()


# ───────────────── Zona Agent (bonus per magazin) ─────────────────

@router.get("/zona-agent", response_model=ZonaAgentsResponse)
async def list_zona_agents(
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows = await svc.list_zona_agents_summary(session, tenant_id, year=y, month=m)
    return ZonaAgentsResponse(
        year=y, month=m,
        agents=[ZonaAgentSummary(**r) for r in rows],
    )


@router.get("/zona-agent/{agent_id}", response_model=ZonaAgentDetail)
async def get_zona_agent(
    agent_id: UUID,
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    detail = await svc.get_zona_agent_detail(
        session, tenant_id, agent_id=agent_id, year=y, month=m,
    )
    if detail is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent inexistent"},
        )
    return ZonaAgentDetail(
        agent_id=detail["agent_id"],
        agent_name=detail["agent_name"],
        year=detail["year"],
        month=detail["month"],
        stores=[ZonaStoreRow(**s) for s in detail["stores"]],
        total_target=detail["total_target"],
        total_realizat=detail["total_realizat"],
        total_bonus=detail["total_bonus"],
    )


@router.put("/zona-agent/bonus", response_model=ZonaStoreRow)
async def upsert_zona_bonus(
    payload: ZonaBonusUpsert,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(payload.year)
    m = _validate_month(payload.month)
    await svc.upsert_zona_bonus(
        session,
        tenant_id=tenant_id,
        agent_id=payload.agent_id,
        store_id=payload.store_id,
        year=y, month=m,
        bonus=payload.bonus,
        note=payload.note,
    )
    await session.commit()
    detail = await svc.get_zona_agent_detail(
        session, tenant_id, agent_id=payload.agent_id, year=y, month=m,
    )
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    match = next(
        (s for s in detail["stores"] if s["store_id"] == payload.store_id), None,
    )
    if match is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "store_not_assigned", "message": "Magazin nealocat agentului"},
        )
    return ZonaStoreRow(**match)


# ───────────────── Matricea Agenți ─────────────────

@router.get("/matrix", response_model=MatrixResponse)
async def get_matrix(
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows_data = await svc.build_matrix(session, tenant_id, year=y, month=m)
    rows = [MatrixRow(**r) for r in rows_data]
    grand_vanzari = sum((r.vanzari for r in rows), Decimal("0"))
    grand_cost = sum((r.total_cost for r in rows), Decimal("0"))
    return MatrixResponse(
        year=y, month=m,
        rows=rows,
        grand_vanzari=grand_vanzari,
        grand_cost=grand_cost,
    )
