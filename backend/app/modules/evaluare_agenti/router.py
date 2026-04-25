from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids, get_current_tenant_id, get_current_user
from app.modules.users.models import User
from app.modules.evaluare_agenti import service as svc
from app.modules.evaluare_agenti.schemas import (
    AgentAnnualMonthRow,
    AgentAnnualResponse,
    AgentCompList,
    AgentCompRow,
    AgentCompUpsert,
    AnnualCostResponse,
    AnnualCostRow,
    BonusMagazinAnnualResponse,
    BonusMagazinAnnualRow,
    DashboardAgentRow,
    DashboardResponse,
    FacturaBonusAcceptRequest,
    FacturaBonusAcceptResponse,
    FacturaBonusList,
    FacturaBonusPendingCount,
    FacturaBonusRow,
    FacturaBonusUnassignRequest,
    FacturaBonusUnassignResponse,
    MonthInputList,
    MonthInputRow,
    MonthInputUpsert,
    RaionBonusCreate,
    RaionBonusList,
    RaionBonusRow,
    RaionBonusUpdate,
    SalariuBonusAnnualResponse,
    SalariuBonusAnnualRow,
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
            bonus_vanzari_eligibil=(comp.bonus_vanzari_eligibil if comp else True),
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    comp = await svc.upsert_compensation_multi(
        session,
        org_ids,
        tenant_id,
        agent_id=payload.agent_id,
        salariu_fix=payload.salariu_fix,
        bonus_vanzari_eligibil=payload.bonus_vanzari_eligibil,
        note=payload.note,
    )
    if comp is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent inexistent"},
        )
    await session.commit()
    from app.modules.agents import service as agents_service
    agent = await agents_service.get_agent(session, tenant_id, payload.agent_id)
    return AgentCompRow(
        agent_id=payload.agent_id,
        agent_name=agent.full_name if agent else "",
        salariu_fix=comp.salariu_fix,
        bonus_vanzari_eligibil=comp.bonus_vanzari_eligibil,
        note=comp.note,
        updated_at=comp.updated_at,
    )


# ───────────────── Input Lunar ─────────────────

@router.get("/month-inputs", response_model=MonthInputList)
async def list_month_inputs(
    year: int = Query(...),
    month: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows_data = await svc.list_month_inputs_merged(
        session, org_ids, current_user.tenant_id, year=y, month=m,
    )
    return MonthInputList(
        year=y,
        month=m,
        rows=[MonthInputRow(year=y, month=m, **r) for r in rows_data],
    )


@router.put("/month-inputs", response_model=MonthInputRow)
async def upsert_month_input(
    payload: MonthInputUpsert,
    tenant_id: UUID = Depends(get_current_tenant_id),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    current_user: User = Depends(get_current_user),
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
        merchandiser_zona=payload.merchandiser_zona,
        cheltuieli_auto=payload.cheltuieli_auto,
        alte_cheltuieli=payload.alte_cheltuieli,
        alte_cheltuieli_label=payload.alte_cheltuieli_label,
        note=payload.note,
    )
    await session.commit()
    rows_data = await svc.list_month_inputs_merged(
        session, org_ids, current_user.tenant_id, year=y, month=m,
    )
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
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    rows = await svc.list_zona_agents_summary_merged(session, org_ids, year=y, month=m)
    return ZonaAgentsResponse(
        year=y, month=m,
        agents=[ZonaAgentSummary(**r) for r in rows],
    )


@router.get("/zona-agent/{agent_id}", response_model=ZonaAgentDetail)
async def get_zona_agent(
    agent_id: UUID,
    year: int = Query(...),
    month: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    m = _validate_month(month)
    detail = await svc.get_zona_agent_detail_merged(
        session, org_ids, current_user.tenant_id, agent_id=agent_id, year=y, month=m,
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


# ───────────────── Analiza costuri anuală ─────────────────

@router.get("/cost-annual", response_model=AnnualCostResponse)
async def get_cost_annual(
    year: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    rows_data = await svc.build_annual_costs_merged(session, org_ids, year=y)
    rows = [AnnualCostRow(**r) for r in rows_data]
    month_totals = [Decimal("0")] * 12
    grand = Decimal("0")
    for r in rows:
        for i, v in enumerate(r.monthly):
            month_totals[i] += v
        grand += r.total
    return AnnualCostResponse(
        year=y, rows=rows,
        month_totals=month_totals,
        grand_total=grand,
    )


@router.get("/agent-annual", response_model=AgentAnnualResponse)
async def get_agent_annual(
    agent_id: UUID = Query(...),
    year: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    data = await svc.build_agent_annual_breakdown_merged(
        session, org_ids, current_user.tenant_id, agent_id=agent_id, year=y,
    )
    if data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_not_found", "message": "Agent inexistent"},
        )
    rows = [AgentAnnualMonthRow(**r) for r in data["rows"]]
    totals = AgentAnnualMonthRow(
        month=0,
        salariu_fix=sum((r.salariu_fix for r in rows), Decimal("0")),
        bonus_agent=sum((r.bonus_agent for r in rows), Decimal("0")),
        merchandiser_zona=sum((r.merchandiser_zona for r in rows), Decimal("0")),
        cheltuieli_auto=sum((r.cheltuieli_auto for r in rows), Decimal("0")),
        alte_cheltuieli=sum((r.alte_cheltuieli for r in rows), Decimal("0")),
        bonus_raion=sum((r.bonus_raion for r in rows), Decimal("0")),
        total=sum((r.total for r in rows), Decimal("0")),
    )
    return AgentAnnualResponse(
        agent_id=data["agent_id"],
        agent_name=data["agent_name"],
        year=y,
        rows=rows,
        column_totals=totals,
    )


# ───────────────── Dashboard agenți ─────────────────

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    year: int = Query(...),
    months: list[int] | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    ms: list[int] | None = None
    if months:
        ms = []
        for m in months:
            if not 1 <= m <= 12:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"code": "invalid_month", "message": "month trebuie între 1 și 12"},
                )
            ms.append(m)
    rows_data = await svc.build_dashboard_merged(session, org_ids, year=y, months=ms)
    rows = [DashboardAgentRow(**r) for r in rows_data]
    grand_v = sum((r.vanzari for r in rows), Decimal("0"))
    grand_c = sum((r.cheltuieli for r in rows), Decimal("0"))
    grand_b = sum((r.bonus_agent for r in rows), Decimal("0"))
    grand_stores = sum((r.store_count for r in rows), 0)
    grand_pct: Decimal | None = None
    if grand_v > 0:
        grand_pct = (grand_c / grand_v * Decimal("100")).quantize(Decimal("0.01"))
    return DashboardResponse(
        year=y,
        month=(ms[0] if ms and len(ms) == 1 else None),
        rows=rows,
        grand_vanzari=grand_v,
        grand_cheltuieli=grand_c,
        grand_bonus_agent=grand_b,
        grand_store_count=grand_stores,
        grand_cost_pct=grand_pct,
    )


@router.get("/salariu-bonus-annual", response_model=SalariuBonusAnnualResponse)
async def get_salariu_bonus_annual(
    year: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    rows_data = await svc.build_salariu_bonus_annual_merged(session, org_ids, year=y)
    rows = [SalariuBonusAnnualRow(**r) for r in rows_data]
    month_totals = [Decimal("0")] * 12
    grand = Decimal("0")
    for r in rows:
        for i, v in enumerate(r.monthly):
            month_totals[i] += v
        grand += r.total
    return SalariuBonusAnnualResponse(
        year=y, rows=rows,
        month_totals=month_totals,
        grand_total=grand,
    )


# ───────────────── Facturi Bonus de Asignat ─────────────────

@router.get("/facturi-bonus/pending-count", response_model=FacturaBonusPendingCount)
async def get_facturi_bonus_pending_count(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.get_facturi_bonus_pending_count(session, tenant_id)
    return FacturaBonusPendingCount(**data)


@router.get("/facturi-bonus", response_model=FacturaBonusList)
async def list_facturi_bonus(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    data = await svc.list_facturi_bonus_pending(session, tenant_id)
    return FacturaBonusList(
        rows=[FacturaBonusRow(**r) for r in data["rows"]],
        pending_count=data["pending_count"],
        pending_amount=data["pending_amount"],
        assigned_count=data["assigned_count"],
        assigned_amount=data["assigned_amount"],
        threshold=data["threshold"],
    )


@router.post("/facturi-bonus/accept", response_model=FacturaBonusAcceptResponse)
async def accept_facturi_bonus(
    payload: FacturaBonusAcceptRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    result = await svc.accept_facturi_bonus(session, tenant_id, payload.ids)
    await session.commit()
    return FacturaBonusAcceptResponse(**result)


@router.post("/facturi-bonus/unassign", response_model=FacturaBonusUnassignResponse)
async def unassign_facturi_bonus(
    payload: FacturaBonusUnassignRequest,
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    result = await svc.unassign_facturi_bonus(session, tenant_id, payload.ids)
    await session.commit()
    return FacturaBonusUnassignResponse(**result)


@router.get("/bonus-magazin-annual", response_model=BonusMagazinAnnualResponse)
async def get_bonus_magazin_annual(
    year: int = Query(...),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    y = _validate_year(year)
    rows_data = await svc.build_bonus_magazin_annual_merged(session, org_ids, year=y)
    rows = [BonusMagazinAnnualRow(**r) for r in rows_data]
    month_totals = [Decimal("0")] * 12
    grand = Decimal("0")
    for r in rows:
        for i, v in enumerate(r.monthly):
            month_totals[i] += v
        grand += r.total
    return BonusMagazinAnnualResponse(
        year=y, rows=rows,
        month_totals=month_totals,
        grand_total=grand,
    )
