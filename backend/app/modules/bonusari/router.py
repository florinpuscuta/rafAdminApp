from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_org_ids
from app.modules.bonusari import service as svc
from app.modules.bonusari.schemas import (
    BonAgentRow,
    BonMonthCell,
    BonMonthTotal,
    BonResponse,
    BonRules,
    BonTier,
)
from app.modules.tenants.models import Organization

router = APIRouter(prefix="/api/bonusari", tags=["bonusari"])

_SCOPES = {"adp", "sika", "sikadp"}
_SCOPE_TO_SLUG = {"adp": "adeplast", "sika": "sika"}


async def _resolve_tenant_for_scope(
    session: AsyncSession, org_ids: list[UUID], scope: str,
) -> UUID:
    """În SIKADP user-ul are 2 org_ids; alegem pe cel cu slug-ul matching.
    Pentru scope='sikadp' returnam primul (service-ul face merging singur)."""
    if len(org_ids) == 1:
        return org_ids[0]
    target_slug = _SCOPE_TO_SLUG.get(scope)
    if target_slug:
        res = await session.execute(
            select(Organization.id).where(
                Organization.id.in_(org_ids),
                Organization.slug == target_slug,
            )
        )
        match = res.scalar_one_or_none()
        if match is not None:
            return match
    return org_ids[0]


def _rules_to_model() -> BonRules:
    return BonRules(
        tiers=[BonTier(threshold_pct=t, amount=a) for t, a in svc.BONUS_TIERS],
        recovery_amount=svc.RECOVERY_AMOUNT,
        recovery_threshold_pct=svc.RECOVERY_THRESHOLD_PCT,
    )


def _month_cell_to_model(c: svc.BonusMonthResult) -> BonMonthCell:
    return BonMonthCell(
        month=c.month,
        month_name=svc.month_name(c.month),
        prev_sales=c.prev_sales,
        curr_sales=c.curr_sales,
        growth_pct=c.growth_pct,
        bonus=c.bonus,
        recovery=c.recovery,
        total=c.total,
        is_future=c.is_future,
    )


def _agent_to_model(a: svc.BonusAgentRow) -> BonAgentRow:
    return BonAgentRow(
        agent_id=a.agent_id,
        agent_name=a.agent_name,
        months=[_month_cell_to_model(m) for m in a.months],
        total_bonus=a.total_bonus,
    )


def _build_response(scope: str, data: dict) -> BonResponse:
    agent_rows = [_agent_to_model(a) for a in data["agents"]]

    # Totaluri per lună (peste toți agenții)
    per_m_bonus: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    per_m_recov: dict[int, Decimal] = {m: Decimal(0) for m in range(1, 13)}
    for ar in agent_rows:
        for mc in ar.months:
            per_m_bonus[mc.month] += mc.bonus
            per_m_recov[mc.month] += mc.recovery

    month_totals = [
        BonMonthTotal(
            month=m, month_name=svc.month_name(m),
            bonus=per_m_bonus[m],
            recovery=per_m_recov[m],
            total=per_m_bonus[m] + per_m_recov[m],
        )
        for m in range(1, 13)
    ]
    grand_total = sum((t.total for t in month_totals), Decimal(0))

    return BonResponse(
        scope=scope,
        year_curr=data["year_curr"],
        year_prev=data["year_prev"],
        current_month_limit=data["current_month_limit"],
        rules=_rules_to_model(),
        last_update=data["last_update"],
        agents=agent_rows,
        month_totals=month_totals,
        grand_total=grand_total,
    )


@router.get("", response_model=BonResponse)
async def get_bonusari(
    scope: str = Query("adp", description="'adp' | 'sika' | 'sikadp'"),
    year: int | None = Query(None, ge=2000, le=2100),
    month: int | None = Query(
        None, ge=1, le=12,
        description="Ultima lună eligibilă (inclusiv). Default: luna curentă "
                    "(dacă year = anul curent) sau 12 (altfel).",
    ),
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

    tenant_id = await _resolve_tenant_for_scope(session, org_ids, scope)

    if scope == "adp":
        data = await svc.get_for_adp(session, tenant_id, year_curr=year_curr, month=month)
    elif scope == "sika":
        data = await svc.get_for_sika(session, tenant_id, year_curr=year_curr, month=month)
    else:
        data = await svc.get_for_sikadp(session, tenant_id, year_curr=year_curr, month=month)

    return _build_response(scope, data)
