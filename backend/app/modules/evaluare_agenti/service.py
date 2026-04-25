from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.evaluare_agenti.models import (
    AgentCompensation,
    AgentMonthInput,
    AgentStoreBonus,
    FacturiBonusDecision,
    StoreContactBonus,
)
from app.modules.bonusari import service as bonusari_service
from app.modules.mappings.resolution import (
    client_sam_map,
    resolve as resolve_canonical,
    store_agent_map,
)
from app.modules.sales.models import RawSale
from app.modules.stores.models import Store
from app.modules.targhet.service import (
    DEFAULT_TARGET_PCT,
    _GROUPS_SIKADP,
    _sales_rows,
    load_growth_pct_map,
)
from app.modules.vz_la_zi.service import _build_rows as _vz_build_rows


def _target_multiplier(pct: Decimal) -> Decimal:
    """Target = prev × (1 + pct/100). Folosit pe (year, month)."""
    return (Decimal("100") + pct) / Decimal("100")


# ───────────────── Pachet Salarial ─────────────────

async def list_compensation(
    session: AsyncSession, tenant_id: UUID,
) -> list[tuple[Agent, AgentCompensation | None]]:
    stmt = (
        select(Agent, AgentCompensation)
        .outerjoin(
            AgentCompensation,
            (AgentCompensation.agent_id == Agent.id)
            & (AgentCompensation.tenant_id == tenant_id),
        )
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )
    res = await session.execute(stmt)
    return [(row.Agent, row.AgentCompensation) for row in res.all()]


async def upsert_compensation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    salariu_fix: Decimal,
    bonus_vanzari_eligibil: bool,
    note: str | None,
) -> AgentCompensation:
    stmt = select(AgentCompensation).where(
        AgentCompensation.tenant_id == tenant_id,
        AgentCompensation.agent_id == agent_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        existing = AgentCompensation(
            tenant_id=tenant_id,
            agent_id=agent_id,
            salariu_fix=salariu_fix,
            bonus_vanzari_eligibil=bonus_vanzari_eligibil,
            note=note,
        )
        session.add(existing)
    else:
        existing.salariu_fix = salariu_fix
        existing.bonus_vanzari_eligibil = bonus_vanzari_eligibil
        existing.note = note
    await session.flush()
    return existing


async def _ineligible_agents(
    session: AsyncSession, tenant_id: UUID,
) -> set[UUID]:
    """Set of agent_id pentru care `bonus_vanzari_eligibil = False`."""
    stmt = select(AgentCompensation.agent_id).where(
        AgentCompensation.tenant_id == tenant_id,
        AgentCompensation.bonus_vanzari_eligibil.is_(False),
    )
    return {r[0] for r in (await session.execute(stmt)).all()}


# ───────────────── Readonly lookups pentru matricea lunară ─────────────────

async def _bonus_by_agent(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> dict[UUID, Decimal]:
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=month,
    )
    ineligible = await _ineligible_agents(session, tenant_id)
    out: dict[UUID, Decimal] = {}
    for agent_row in bonus_data.get("agents", []):
        aid = agent_row.agent_id
        if aid is None or aid in ineligible:
            continue
        month_cell = next((m for m in agent_row.months if m.month == month), None)
        if month_cell is not None and not month_cell.is_future:
            out[aid] = month_cell.total
    return out


async def _raion_bonus_by_agent(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> dict[UUID, Decimal]:
    """Suma bonusurilor per agent pe toate magazinele lui (tabel Zona Agent)."""
    stmt = (
        select(
            AgentStoreBonus.agent_id,
            func.coalesce(func.sum(AgentStoreBonus.bonus), 0).label("suma"),
        )
        .where(
            AgentStoreBonus.tenant_id == tenant_id,
            AgentStoreBonus.year == year,
            AgentStoreBonus.month == month,
        )
        .group_by(AgentStoreBonus.agent_id)
    )
    return {
        r.agent_id: Decimal(r.suma)
        for r in (await session.execute(stmt)).all()
    }


# ───────────────── Zona Agent (magazine per agent) ─────────────────

async def _agent_zone_stores(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> dict[UUID, set[UUID]]:
    """{agent_id: {store_id, ...}} — alocarea agent→magazine identică cu
    Vz la zi SIKADP pentru luna dată.

    Sursă: aceeași rezoluție canonică (SAM client_sam_map + store_map) pe
    raw_sales (sales_xlsx + sika_mtd_xlsx/sika_xlsx, KA) + raw_orders (ADP + Sika)
    pentru (year_prev, month) și (year, month). Orice (agent, store) ce apare
    în Vz la zi apare și aici.
    """
    rows, _ = await _vz_build_rows(
        session, tenant_id,
        year_curr=year, month=month,
        sales_batch_sources=["sales_xlsx", "sika_mtd_xlsx", "sika_xlsx"],
        orders_source=None,
    )
    # Vz la zi sikadp combină ADP + Sika ca două apeluri; pentru allocation
    # e suficient set-ul unificat de perechi (agent, store). Adăugăm și
    # sursele de orders (ADP + Sika) ca să captăm și magazine fără vânzări.
    for orders_src in ("adp", "sika"):
        more, _ = await _vz_build_rows(
            session, tenant_id,
            year_curr=year, month=month,
            sales_batch_sources=[],
            orders_source=orders_src,
        )
        rows.update(more)

    out: dict[UUID, set[UUID]] = {}
    for (agent_id, store_id) in rows.keys():
        if agent_id is None or store_id is None:
            continue
        out.setdefault(agent_id, set()).add(store_id)
    return out


async def _sikadp_sales_by_agent_store(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> dict[tuple[UUID | None, UUID | None], tuple[Decimal, Decimal]]:
    """(agent_canonical, store_canonical) → (prev_sales, curr_sales) pentru
    luna specificată.

    Reutilizează exact pipeline-ul targhet sikadp: surse (sales_xlsx +
    sika_mtd_xlsx/sika_xlsx cu dedup per grup), canal KA, rezoluție
    canonică via SAM. Numerele obținute coincid cu cele din pagina Targhet.
    """
    rows_all = await _sales_rows(
        session, tenant_id,
        year_curr=year, batch_source_groups=_GROUPS_SIKADP,
    )
    rows = [r for r in rows_all if r["month"] == month]

    c_map = await client_sam_map(session, tenant_id)
    store_ids_to_resolve: set[UUID] = {
        r["store_id"] for r in rows
        if r["agent_id"] is None and r["store_id"] is not None
    }
    s_map = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    out: dict[tuple[UUID | None, UUID | None], tuple[Decimal, Decimal]] = {}
    for r in rows:
        agent_c, store_c = resolve_canonical(
            agent_id=r["agent_id"], store_id=r["store_id"], client=r.get("client"),
            client_map=c_map, store_map=s_map,
        )
        key = (agent_c, store_c)
        prev, curr = out.get(key, (Decimal("0"), Decimal("0")))
        if r["year"] == year - 1:
            prev += r["amount"]
        elif r["year"] == year:
            curr += r["amount"]
        out[key] = (prev, curr)
    return out


async def list_zona_agents_summary(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> list[dict]:
    """Pentru fiecare agent activ: numărul de magazine din zonă + totaluri."""
    agents_stmt = (
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )
    agent_rows = (await session.execute(agents_stmt)).all()

    bonus_sum_stmt = (
        select(
            AgentStoreBonus.agent_id,
            func.coalesce(func.sum(AgentStoreBonus.bonus), 0).label("total"),
        )
        .where(
            AgentStoreBonus.tenant_id == tenant_id,
            AgentStoreBonus.year == year,
            AgentStoreBonus.month == month,
        )
        .group_by(AgentStoreBonus.agent_id)
    )
    bonus_by_agent: dict[UUID, Decimal] = {
        r.agent_id: Decimal(r.total)
        for r in (await session.execute(bonus_sum_stmt)).all()
    }

    stores_by_agent = await _agent_zone_stores(
        session, tenant_id, year=year, month=month,
    )
    sales = await _sikadp_sales_by_agent_store(
        session, tenant_id, year=year, month=month,
    )
    pct_map = await load_growth_pct_map(session, tenant_id, year=year)
    multiplier = _target_multiplier(pct_map.get(month, DEFAULT_TARGET_PCT))

    out: list[dict] = []
    for r in agent_rows:
        aid: UUID = r.id
        stores = stores_by_agent.get(aid, set())
        total_prev = Decimal("0")
        total_curr = Decimal("0")
        for sid in stores:
            prev, curr = sales.get((aid, sid), (Decimal("0"), Decimal("0")))
            total_prev += prev
            total_curr += curr
        out.append({
            "agent_id": aid,
            "agent_name": r.full_name,
            "store_count": len(stores),
            "total_target": (total_prev * multiplier).quantize(Decimal("0.01")),
            "total_realizat": total_curr,
            "total_bonus": bonus_by_agent.get(aid, Decimal("0")),
        })
    return out


async def get_zona_agent_detail(
    session: AsyncSession, tenant_id: UUID, *,
    agent_id: UUID, year: int, month: int,
) -> dict | None:
    agent = (await session.execute(
        select(Agent).where(Agent.tenant_id == tenant_id, Agent.id == agent_id)
    )).scalar_one_or_none()
    if agent is None:
        return None

    all_zones = await _agent_zone_stores(
        session, tenant_id, year=year, month=month,
    )
    store_ids = sorted(all_zones.get(agent_id, set()))
    if not store_ids:
        return {
            "agent_id": agent.id, "agent_name": agent.full_name,
            "year": year, "month": month,
            "stores": [],
            "total_target": Decimal("0"),
            "total_realizat": Decimal("0"),
            "total_bonus": Decimal("0"),
        }

    # Store names
    stores_stmt = select(Store.id, Store.name).where(
        Store.tenant_id == tenant_id, Store.id.in_(store_ids),
    )
    names = {r.id: r.name for r in (await session.execute(stores_stmt)).all()}

    sales = await _sikadp_sales_by_agent_store(
        session, tenant_id, year=year, month=month,
    )
    pct_map = await load_growth_pct_map(session, tenant_id, year=year)
    multiplier = _target_multiplier(pct_map.get(month, DEFAULT_TARGET_PCT))

    # Bonusurile deja introduse pentru agentul ăsta, luna asta
    bonus_stmt = select(AgentStoreBonus).where(
        AgentStoreBonus.tenant_id == tenant_id,
        AgentStoreBonus.agent_id == agent_id,
        AgentStoreBonus.year == year,
        AgentStoreBonus.month == month,
    )
    bonus_by_store: dict[UUID, AgentStoreBonus] = {
        b.store_id: b for b in (await session.execute(bonus_stmt)).scalars().all()
    }

    rows: list[dict] = []
    total_target = Decimal("0")
    total_realizat = Decimal("0")
    total_bonus = Decimal("0")
    for sid in store_ids:
        prev, curr = sales.get((agent_id, sid), (Decimal("0"), Decimal("0")))
        target = (prev * multiplier).quantize(Decimal("0.01"))
        ach: Decimal | None = None
        if target > 0:
            ach = ((curr / target) * Decimal("100")).quantize(Decimal("0.01"))
        existing = bonus_by_store.get(sid)
        bonus = existing.bonus if existing else Decimal("0")
        note = existing.note if existing else None
        total_target += target
        total_realizat += curr
        total_bonus += bonus
        rows.append({
            "store_id": sid,
            "store_name": names.get(sid, "— magazin —"),
            "target": target,
            "realizat": curr,
            "achievement_pct": ach,
            "bonus": bonus,
            "note": note,
        })
    rows.sort(key=lambda r: r["store_name"])

    return {
        "agent_id": agent.id,
        "agent_name": agent.full_name,
        "year": year,
        "month": month,
        "stores": rows,
        "total_target": total_target,
        "total_realizat": total_realizat,
        "total_bonus": total_bonus,
    }


async def upsert_zona_bonus(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    store_id: UUID,
    year: int,
    month: int,
    bonus: Decimal,
    note: str | None,
) -> AgentStoreBonus:
    stmt = select(AgentStoreBonus).where(
        AgentStoreBonus.tenant_id == tenant_id,
        AgentStoreBonus.agent_id == agent_id,
        AgentStoreBonus.store_id == store_id,
        AgentStoreBonus.year == year,
        AgentStoreBonus.month == month,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        existing = AgentStoreBonus(
            tenant_id=tenant_id,
            agent_id=agent_id,
            store_id=store_id,
            year=year,
            month=month,
            bonus=bonus,
            note=note,
        )
        session.add(existing)
    else:
        existing.bonus = bonus
        existing.note = note
    await session.flush()
    return existing


# ───────────────── Input Lunar ─────────────────

async def list_month_inputs(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> list[dict]:
    """Matricea lunară: per agent activ — vânzări + sal. fix + bonus + costuri directe + bonus raion."""
    bonus_by_ag = await _bonus_by_agent(session, tenant_id, year=year, month=month)
    raion_by_ag = await _raion_bonus_by_agent(session, tenant_id, year=year, month=month)

    sales_stmt = (
        select(
            RawSale.agent_id,
            func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
        )
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.year == year,
            RawSale.month == month,
            RawSale.agent_id.is_not(None),
        )
        .group_by(RawSale.agent_id)
    )
    sales_by_agent: dict[UUID, Decimal] = {
        r.agent_id: Decimal(r.amt) for r in (await session.execute(sales_stmt)).all()
    }

    stmt = (
        select(Agent, AgentCompensation, AgentMonthInput)
        .outerjoin(
            AgentCompensation,
            (AgentCompensation.agent_id == Agent.id)
            & (AgentCompensation.tenant_id == tenant_id),
        )
        .outerjoin(
            AgentMonthInput,
            (AgentMonthInput.agent_id == Agent.id)
            & (AgentMonthInput.tenant_id == tenant_id)
            & (AgentMonthInput.year == year)
            & (AgentMonthInput.month == month),
        )
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )
    res = await session.execute(stmt)
    out = []
    for row in res.all():
        agent: Agent = row.Agent
        comp: AgentCompensation | None = row.AgentCompensation
        mi: AgentMonthInput | None = row.AgentMonthInput

        vanzari = sales_by_agent.get(agent.id, Decimal("0"))
        salariu_fix = comp.salariu_fix if comp else Decimal("0")
        bonus_agent = bonus_by_ag.get(agent.id, Decimal("0"))
        bonus_raion = raion_by_ag.get(agent.id, Decimal("0"))
        merch = mi.merchandiser_zona_ron if mi else Decimal("0")
        auto = mi.cheltuieli_auto_ron if mi else Decimal("0")
        alte = mi.alte_cheltuieli_ron if mi else Decimal("0")
        alte_label = mi.alte_cheltuieli_label if mi else None
        total = salariu_fix + bonus_agent + merch + auto + alte + bonus_raion

        out.append({
            "agent_id": agent.id,
            "agent_name": agent.full_name,
            "vanzari": vanzari,
            "salariu_fix": salariu_fix,
            "bonus_agent": bonus_agent,
            "bonus_raion": bonus_raion,
            "merchandiser_zona": merch,
            "cheltuieli_auto": auto,
            "alte_cheltuieli": alte,
            "alte_cheltuieli_label": alte_label,
            "total_cost": total,
            "note": mi.note if mi else None,
        })
    out.sort(key=lambda r: (-r["vanzari"], r["agent_name"].lower()))
    return out


async def upsert_month_input(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    year: int,
    month: int,
    merchandiser_zona: Decimal,
    cheltuieli_auto: Decimal,
    alte_cheltuieli: Decimal,
    alte_cheltuieli_label: str | None,
    note: str | None,
) -> AgentMonthInput:
    stmt = select(AgentMonthInput).where(
        AgentMonthInput.tenant_id == tenant_id,
        AgentMonthInput.agent_id == agent_id,
        AgentMonthInput.year == year,
        AgentMonthInput.month == month,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is None:
        existing = AgentMonthInput(
            tenant_id=tenant_id,
            agent_id=agent_id,
            year=year,
            month=month,
            merchandiser_zona_ron=merchandiser_zona,
            cheltuieli_auto_ron=cheltuieli_auto,
            alte_cheltuieli_ron=alte_cheltuieli,
            alte_cheltuieli_label=alte_cheltuieli_label,
            note=note,
        )
        session.add(existing)
    else:
        existing.merchandiser_zona_ron = merchandiser_zona
        existing.cheltuieli_auto_ron = cheltuieli_auto
        existing.alte_cheltuieli_ron = alte_cheltuieli
        existing.alte_cheltuieli_label = alte_cheltuieli_label
        existing.note = note
    await session.flush()
    return existing


# ───────────────── Bonusări Oameni Raion ─────────────────

async def list_raion_bonus(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> list[dict]:
    stmt = (
        select(StoreContactBonus, Store, Agent)
        .join(Store, Store.id == StoreContactBonus.store_id)
        .outerjoin(Agent, Agent.id == StoreContactBonus.agent_id)
        .where(
            StoreContactBonus.tenant_id == tenant_id,
            StoreContactBonus.year == year,
            StoreContactBonus.month == month,
        )
        .order_by(Store.name, StoreContactBonus.contact_name)
    )
    res = await session.execute(stmt)
    out = []
    for row in res.all():
        b: StoreContactBonus = row.StoreContactBonus
        s: Store = row.Store
        a: Agent | None = row.Agent
        out.append({
            "id": b.id,
            "store_id": b.store_id,
            "store_name": s.name,
            "agent_id": b.agent_id,
            "agent_name": a.full_name if a else None,
            "year": b.year,
            "month": b.month,
            "contact_name": b.contact_name,
            "suma": b.suma,
            "note": b.note,
        })
    return out


async def create_raion_bonus(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    store_id: UUID,
    year: int,
    month: int,
    contact_name: str,
    suma: Decimal,
    note: str | None,
) -> StoreContactBonus:
    from app.modules.agents.models import AgentStoreAssignment
    agent_id_stmt = (
        select(AgentStoreAssignment.agent_id)
        .where(
            AgentStoreAssignment.tenant_id == tenant_id,
            AgentStoreAssignment.store_id == store_id,
        )
        .limit(1)
    )
    agent_id = (await session.execute(agent_id_stmt)).scalar_one_or_none()

    row = StoreContactBonus(
        tenant_id=tenant_id,
        store_id=store_id,
        agent_id=agent_id,
        year=year,
        month=month,
        contact_name=contact_name,
        suma=suma,
        note=note,
    )
    session.add(row)
    await session.flush()
    return row


async def update_raion_bonus(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    id_: UUID,
    contact_name: str,
    suma: Decimal,
    note: str | None,
) -> StoreContactBonus | None:
    stmt = select(StoreContactBonus).where(
        StoreContactBonus.tenant_id == tenant_id,
        StoreContactBonus.id == id_,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    row.contact_name = contact_name
    row.suma = suma
    row.note = note
    await session.flush()
    return row


async def delete_raion_bonus(
    session: AsyncSession, *, tenant_id: UUID, id_: UUID,
) -> bool:
    stmt = select(StoreContactBonus).where(
        StoreContactBonus.tenant_id == tenant_id,
        StoreContactBonus.id == id_,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True


# ───────────────── Analiza costuri anuală (12 luni × agenți) ─────────────────

async def build_annual_costs(
    session: AsyncSession, tenant_id: UUID, *, year: int,
) -> list[dict]:
    """Pentru fiecare agent activ: cost total pe fiecare lună a anului +
    grand total pe agent. Folosit de pagina 'Analiza costuri zona an'.

    Formula = aceeași cu `build_matrix`:
      total_cost = salariu_fix + bonus_agent[m] + merchandiser_zona[m]
                 + cheltuieli_auto[m] + alte_cheltuieli[m] + bonus_raion[m]
    """
    agents_stmt = (
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )
    agents = (await session.execute(agents_stmt)).all()

    comp_stmt = select(AgentCompensation).where(
        AgentCompensation.tenant_id == tenant_id,
    )
    salariu_by_agent: dict[UUID, Decimal] = {
        c.agent_id: c.salariu_fix
        for c in (await session.execute(comp_stmt)).scalars().all()
    }

    mi_stmt = select(AgentMonthInput).where(
        AgentMonthInput.tenant_id == tenant_id,
        AgentMonthInput.year == year,
    )
    mi_rows = (await session.execute(mi_stmt)).scalars().all()
    mi_by: dict[tuple[UUID, int], AgentMonthInput] = {
        (m.agent_id, m.month): m for m in mi_rows
    }

    # Bonusări sikadp pentru tot anul (o singură chemare).
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=None,
    )
    ineligible = await _ineligible_agents(session, tenant_id)
    bonus_by: dict[tuple[UUID, int], Decimal] = {}
    for ag_row in bonus_data.get("agents", []):
        aid = ag_row.agent_id
        if aid is None or aid in ineligible:
            continue
        for cell in ag_row.months:
            if cell.is_future:
                continue
            bonus_by[(aid, cell.month)] = cell.total

    # Bonus raion pe (agent, month) pentru anul întreg.
    raion_stmt = (
        select(
            StoreContactBonus.agent_id,
            StoreContactBonus.month,
            func.coalesce(func.sum(StoreContactBonus.suma), 0).label("suma"),
        )
        .where(
            StoreContactBonus.tenant_id == tenant_id,
            StoreContactBonus.year == year,
            StoreContactBonus.agent_id.is_not(None),
        )
        .group_by(StoreContactBonus.agent_id, StoreContactBonus.month)
    )
    raion_by: dict[tuple[UUID, int], Decimal] = {
        (r.agent_id, r.month): Decimal(r.suma)
        for r in (await session.execute(raion_stmt)).all()
    }

    out: list[dict] = []
    for a in agents:
        aid: UUID = a.id
        salariu_fix = salariu_by_agent.get(aid, Decimal("0"))
        monthly: list[Decimal] = []
        total_agent = Decimal("0")
        for m in range(1, 13):
            mi = mi_by.get((aid, m))
            merch = mi.merchandiser_zona_ron if mi else Decimal("0")
            auto = mi.cheltuieli_auto_ron if mi else Decimal("0")
            alte = mi.alte_cheltuieli_ron if mi else Decimal("0")
            bon = bonus_by.get((aid, m), Decimal("0"))
            ra = raion_by.get((aid, m), Decimal("0"))
            total_m = salariu_fix + bon + merch + auto + alte + ra
            monthly.append(total_m)
            total_agent += total_m
        out.append({
            "agent_id": aid,
            "agent_name": a.full_name,
            "monthly": monthly,
            "total": total_agent,
        })
    out.sort(key=lambda r: (-r["total"], r["agent_name"].lower()))
    return out


async def build_dashboard(
    session: AsyncSession, tenant_id: UUID, *, year: int,
    months: list[int] | None = None,
) -> list[dict]:
    """Dashboard per agent: nr. magazine, vânzări, cheltuieli, % chelt./vânz,
    cost/100k, creștere YoY, bonus agent. `months=None` / listă goală →
    an întreg (auto-limitat la lunile trecute pentru anul curent); altfel →
    doar lunile selectate.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    if year == now.year:
        current_month_limit = now.month
    elif year > now.year:
        current_month_limit = 0
    else:
        current_month_limit = 12

    # Normalize months: None/empty → year mode (auto-limit); altfel → unique set
    if months:
        months_set = sorted({m for m in months if 1 <= m <= 12})
    else:
        months_set = []
    is_full_year = not months_set

    # Lunile active (pentru multiplicare salariu fix + filtre SQL fair)
    if is_full_year:
        active_months = list(range(1, current_month_limit + 1)) if current_month_limit > 0 else []
    else:
        if year > now.year:
            active_months = []
        elif year == now.year:
            active_months = [m for m in months_set if m <= current_month_limit]
        else:
            active_months = months_set
    months_used = len(active_months)

    # Agenții activi
    agents = (await session.execute(
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )).all()

    # Compensation (salariu fix per agent)
    comp_rows = (await session.execute(
        select(AgentCompensation).where(AgentCompensation.tenant_id == tenant_id)
    )).scalars().all()
    salariu_by: dict[UUID, Decimal] = {c.agent_id: c.salariu_fix for c in comp_rows}

    # Month inputs (merchandiser/auto/alte) — scope filtrat
    mi_stmt = select(AgentMonthInput).where(
        AgentMonthInput.tenant_id == tenant_id,
        AgentMonthInput.year == year,
    )
    if not is_full_year:
        mi_stmt = mi_stmt.where(AgentMonthInput.month.in_(months_set))
    mi_rows = (await session.execute(mi_stmt)).scalars().all()
    mi_totals: dict[UUID, Decimal] = {}
    for mi in mi_rows:
        s = mi.merchandiser_zona_ron + mi.cheltuieli_auto_ron + mi.alte_cheltuieli_ron
        mi_totals[mi.agent_id] = mi_totals.get(mi.agent_id, Decimal("0")) + s

    # Bonus agent (prin bonusari — o singură chemare)
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=None,
    )
    ineligible = await _ineligible_agents(session, tenant_id)
    bonus_agent_by: dict[UUID, Decimal] = {}
    for ag_row in bonus_data.get("agents", []):
        aid = ag_row.agent_id
        if aid is None or aid in ineligible:
            continue
        s = Decimal("0")
        for cell in ag_row.months:
            if cell.is_future:
                continue
            if not is_full_year and cell.month not in months_set:
                continue
            s += cell.total
        bonus_agent_by[aid] = s

    # Bonus raion
    raion_stmt = (
        select(
            StoreContactBonus.agent_id,
            func.coalesce(func.sum(StoreContactBonus.suma), 0).label("suma"),
        )
        .where(
            StoreContactBonus.tenant_id == tenant_id,
            StoreContactBonus.year == year,
            StoreContactBonus.agent_id.is_not(None),
        )
        .group_by(StoreContactBonus.agent_id)
    )
    if not is_full_year:
        raion_stmt = raion_stmt.where(StoreContactBonus.month.in_(months_set))
    raion_by: dict[UUID, Decimal] = {
        r.agent_id: Decimal(r.suma)
        for r in (await session.execute(raion_stmt)).all()
    }

    # Vânzări (current + prev year, pentru YoY) — aliniate pe aceleași luni
    def _sales_stmt(y: int):
        s = (
            select(
                RawSale.agent_id,
                func.coalesce(func.sum(RawSale.amount), 0).label("amt"),
            )
            .where(
                RawSale.tenant_id == tenant_id,
                RawSale.year == y,
                RawSale.agent_id.is_not(None),
            )
            .group_by(RawSale.agent_id)
        )
        if not is_full_year:
            s = s.where(RawSale.month.in_(months_set))
        else:
            if current_month_limit > 0:
                s = s.where(RawSale.month <= current_month_limit)
        return s

    vanzari_by: dict[UUID, Decimal] = {
        r.agent_id: Decimal(r.amt)
        for r in (await session.execute(_sales_stmt(year))).all()
    }
    vanzari_prev_by: dict[UUID, Decimal] = {
        r.agent_id: Decimal(r.amt)
        for r in (await session.execute(_sales_stmt(year - 1))).all()
    }

    # Nr. magazine — luna de referință: ultima selecție / ultima activă / 12
    if months_set:
        ref_month = max(months_set)
    elif current_month_limit > 0:
        ref_month = current_month_limit
    else:
        ref_month = 12
    stores_by: dict[UUID, set[UUID]] = {}
    if ref_month >= 1:
        try:
            stores_by = await _agent_zone_stores(
                session, tenant_id, year=year, month=ref_month,
            )
        except Exception:
            stores_by = {}

    out: list[dict] = []
    for a in agents:
        aid: UUID = a.id
        vanzari = vanzari_by.get(aid, Decimal("0"))
        vanzari_prev = vanzari_prev_by.get(aid, Decimal("0"))
        bonus_ag = bonus_agent_by.get(aid, Decimal("0"))
        raion = raion_by.get(aid, Decimal("0"))
        mi_sum = mi_totals.get(aid, Decimal("0"))
        salariu_total = salariu_by.get(aid, Decimal("0")) * Decimal(months_used)
        cheltuieli = salariu_total + bonus_ag + raion + mi_sum

        cost_pct: Decimal | None = None
        cost_per_100k: Decimal | None = None
        if vanzari > 0:
            cost_pct = (cheltuieli / vanzari * Decimal("100")).quantize(Decimal("0.01"))
            cost_per_100k = (cheltuieli / (vanzari / Decimal("100000"))).quantize(Decimal("0.01"))

        yoy_pct: Decimal | None = None
        if vanzari_prev > 0:
            yoy_pct = ((vanzari - vanzari_prev) / vanzari_prev * Decimal("100")).quantize(Decimal("0.01"))

        store_count = len(stores_by.get(aid, set()))
        out.append({
            "agent_id": aid,
            "agent_name": a.full_name,
            "store_count": store_count,
            "vanzari": vanzari,
            "vanzari_prev": vanzari_prev,
            "cheltuieli": cheltuieli,
            "cost_pct": cost_pct,
            "cost_per_100k": cost_per_100k,
            "yoy_pct": yoy_pct,
            "bonus_agent": bonus_ag,
        })
    out.sort(key=lambda r: (-r["vanzari"], r["agent_name"].lower()))
    return out


async def build_salariu_bonus_annual(
    session: AsyncSession, tenant_id: UUID, *, year: int,
) -> list[dict]:
    """Matrice salariu fix + bonus agent per agent × lună. Pentru fiecare
    (agent, lună) = salariu_fix + bonus_agent[lună]. Lunile viitoare sunt 0.
    """
    agents = (await session.execute(
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )).all()

    comp_rows = (await session.execute(
        select(AgentCompensation).where(AgentCompensation.tenant_id == tenant_id)
    )).scalars().all()
    salariu_by: dict[UUID, Decimal] = {c.agent_id: c.salariu_fix for c in comp_rows}

    # Bonus agent per lună din serviciul bonusari
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=None,
    )
    ineligible = await _ineligible_agents(session, tenant_id)
    bonus_grid: dict[UUID, dict[int, Decimal]] = {}
    future_grid: dict[UUID, dict[int, bool]] = {}
    for ag_row in bonus_data.get("agents", []):
        aid = ag_row.agent_id
        if aid is None:
            continue
        b_month = bonus_grid.setdefault(aid, {})
        f_month = future_grid.setdefault(aid, {})
        for cell in ag_row.months:
            b_month[cell.month] = cell.total
            f_month[cell.month] = cell.is_future

    out: list[dict] = []
    for a in agents:
        aid: UUID = a.id
        sal_fix = salariu_by.get(aid, Decimal("0"))
        is_inelig = aid in ineligible
        monthly: list[Decimal] = []
        for m in range(1, 13):
            is_future = future_grid.get(aid, {}).get(m, False)
            if is_future:
                monthly.append(Decimal("0"))
            else:
                bonus_m = Decimal("0") if is_inelig else bonus_grid.get(aid, {}).get(m, Decimal("0"))
                monthly.append(sal_fix + bonus_m)
        out.append({
            "agent_id": aid,
            "agent_name": a.full_name,
            "monthly": monthly,
            "total": sum(monthly, Decimal("0")),
        })
    out.sort(key=lambda r: (-r["total"], r["agent_name"].lower()))
    return out


async def build_bonus_magazin_annual(
    session: AsyncSession, tenant_id: UUID, *, year: int,
) -> list[dict]:
    """Matrice bonus magazin per agent × lună (1..12) pentru un an. Sursa:
    AgentStoreBonus (bonusurile din „Input bonus magazin", sumate pe agent).
    Sortate desc după total.
    """
    agents = (await session.execute(
        select(Agent.id, Agent.full_name)
        .where(Agent.tenant_id == tenant_id, Agent.active.is_(True))
        .order_by(Agent.full_name)
    )).all()

    stmt = (
        select(
            AgentStoreBonus.agent_id,
            AgentStoreBonus.month,
            func.coalesce(func.sum(AgentStoreBonus.bonus), 0).label("suma"),
        )
        .where(
            AgentStoreBonus.tenant_id == tenant_id,
            AgentStoreBonus.year == year,
        )
        .group_by(AgentStoreBonus.agent_id, AgentStoreBonus.month)
    )
    grid: dict[UUID, list[Decimal]] = {}
    for r in (await session.execute(stmt)).all():
        bucket = grid.setdefault(r.agent_id, [Decimal("0")] * 12)
        if 1 <= r.month <= 12:
            bucket[r.month - 1] = Decimal(r.suma)

    out: list[dict] = []
    for a in agents:
        monthly = grid.get(a.id, [Decimal("0")] * 12)
        out.append({
            "agent_id": a.id,
            "agent_name": a.full_name,
            "monthly": monthly,
            "total": sum(monthly, Decimal("0")),
        })
    out.sort(key=lambda r: (-r["total"], r["agent_name"].lower()))
    return out


async def build_agent_annual_breakdown(
    session: AsyncSession, tenant_id: UUID, *, agent_id: UUID, year: int,
) -> dict | None:
    """Defalcare pe 12 luni pentru un singur agent: salariu fix, bonus agent,
    merchandiser zonă, cheltuieli auto, alte cheltuieli, bonus raion, total.
    Rândul-total de jos se calculează în router.
    """
    agent = (await session.execute(
        select(Agent).where(Agent.tenant_id == tenant_id, Agent.id == agent_id)
    )).scalar_one_or_none()
    if agent is None:
        return None

    comp = (await session.execute(
        select(AgentCompensation).where(
            AgentCompensation.tenant_id == tenant_id,
            AgentCompensation.agent_id == agent_id,
        )
    )).scalar_one_or_none()
    salariu_fix = comp.salariu_fix if comp else Decimal("0")

    mi_rows = (await session.execute(
        select(AgentMonthInput).where(
            AgentMonthInput.tenant_id == tenant_id,
            AgentMonthInput.agent_id == agent_id,
            AgentMonthInput.year == year,
        )
    )).scalars().all()
    mi_by_m: dict[int, AgentMonthInput] = {m.month: m for m in mi_rows}

    is_inelig = bool(comp and not comp.bonus_vanzari_eligibil)
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=None,
    )
    bonus_by_m: dict[int, Decimal] = {}
    if not is_inelig:
        for ag_row in bonus_data.get("agents", []):
            if ag_row.agent_id != agent_id:
                continue
            for cell in ag_row.months:
                if cell.is_future:
                    continue
                bonus_by_m[cell.month] = cell.total
            break

    raion_stmt = (
        select(
            StoreContactBonus.month,
            func.coalesce(func.sum(StoreContactBonus.suma), 0).label("suma"),
        )
        .where(
            StoreContactBonus.tenant_id == tenant_id,
            StoreContactBonus.agent_id == agent_id,
            StoreContactBonus.year == year,
        )
        .group_by(StoreContactBonus.month)
    )
    raion_by_m: dict[int, Decimal] = {
        r.month: Decimal(r.suma)
        for r in (await session.execute(raion_stmt)).all()
    }

    rows: list[dict] = []
    for m in range(1, 13):
        mi = mi_by_m.get(m)
        merch = mi.merchandiser_zona_ron if mi else Decimal("0")
        auto = mi.cheltuieli_auto_ron if mi else Decimal("0")
        alte = mi.alte_cheltuieli_ron if mi else Decimal("0")
        bon = bonus_by_m.get(m, Decimal("0"))
        ra = raion_by_m.get(m, Decimal("0"))
        total = salariu_fix + bon + merch + auto + alte + ra
        rows.append({
            "month": m,
            "salariu_fix": salariu_fix,
            "bonus_agent": bon,
            "merchandiser_zona": merch,
            "cheltuieli_auto": auto,
            "alte_cheltuieli": alte,
            "bonus_raion": ra,
            "total": total,
        })

    return {
        "agent_id": agent.id,
        "agent_name": agent.full_name,
        "year": year,
        "rows": rows,
    }


# ───────────────── Facturi Bonus de Asignat ─────────────────
#
# Regulă:
#   - facturile < -200.000 RON emise central pe clienți KA sunt adesea
#     distribuite aiurea pe magazine și agenți individuali;
#   - acestea trebuie re-atribuite:
#       agent → "Florin Puscuta" (bucket neutru, nu afectează bonusul altora)
#       store → "<CHAIN> | CENTRALA" (magazinul sediu al chain-ului)
#   - totalurile pe firmă rămân neschimbate (amount neatins).
#   - toate reasignările sunt copiate în `raw_sales_reassign_backup` ca
#     punct de întoarcere.

FACTURI_BONUS_THRESHOLD = Decimal("-75000")
# Rânduri administrative (storno / note de credit): product_code e NULL și
# valoarea e materială (|amount| > prag). Astea trec peste threshold-ul de
# bonus pentru că pot fi pozitive, dar nu sunt vânzări reale de produs, deci
# se rutează la fel ca facturile de bonus (Puscuta + CENTRALA).
FACTURI_BONUS_ADMIN_MIN_ABS = Decimal("75000")


def _facturi_bonus_filter():
    """Predicat SQLAlchemy: rânduri tratate ca "bonus contractual" pentru reasignare."""
    return or_(
        RawSale.amount < FACTURI_BONUS_THRESHOLD,
        (RawSale.product_code.is_(None))
        & (func.abs(RawSale.amount) > FACTURI_BONUS_ADMIN_MIN_ABS),
    )


_KA_CHAIN_PATTERNS = [
    "LEROY MERLIN",
    "DEDEMAN",
    "ALTEX",
    "HORNBACH",
    "BRICOSTORE",
    "PUSKIN",
]
_TARGET_AGENT_NAME = "Florin Puscuta"
_REASSIGN_REASON = "facturi_bonus_menu_accept"


def _chain_of(client: str) -> str | None:
    if not client:
        return None
    up = client.upper()
    for p in _KA_CHAIN_PATTERNS:
        if p in up:
            return p
    return None


async def _resolve_target_agent(
    session: AsyncSession, tenant_id: UUID,
) -> Agent | None:
    stmt = select(Agent).where(
        Agent.tenant_id == tenant_id,
        Agent.full_name == _TARGET_AGENT_NAME,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _resolve_centrala_stores(
    session: AsyncSession, tenant_id: UUID,
) -> dict[str, Store]:
    """Mapează pattern-ul KA (ex: 'LEROY MERLIN') la magazinul Centrala."""
    stmt = select(Store).where(
        Store.tenant_id == tenant_id,
        Store.active.is_(True),
        Store.name.ilike("%CENTRALA%"),
    )
    res = (await session.execute(stmt)).scalars().all()
    out: dict[str, Store] = {}
    for s in res:
        name_up = (s.name or "").upper()
        chain_up = (s.chain or "").upper()
        for p in _KA_CHAIN_PATTERNS:
            if p in name_up or p in chain_up:
                if p not in out:
                    out[p] = s
                break
    # Fallback pentru DEDEMAN: folosim "Sediul Central" dacă nu avem "CENTRALA"
    if "DEDEMAN" not in out:
        stmt2 = select(Store).where(
            Store.tenant_id == tenant_id,
            Store.active.is_(True),
            Store.name.ilike("%Sediul Central%"),
        )
        ded = (await session.execute(stmt2)).scalars().first()
        if ded is not None:
            out["DEDEMAN"] = ded
    return out


async def _load_decisions_map(
    session: AsyncSession, tenant_id: UUID,
) -> dict[tuple[int, int, str, Decimal], FacturiBonusDecision]:
    """{(year, month, client, amount): decision} — cheie stabilă între re-import-uri."""
    stmt = select(FacturiBonusDecision).where(
        FacturiBonusDecision.tenant_id == tenant_id,
    )
    rows = (await session.execute(stmt)).scalars().all()
    return {(d.year, d.month, d.client, d.amount): d for d in rows}


async def _backup_and_reassign(
    session: AsyncSession,
    *,
    rs: RawSale,
    tenant_id: UUID,
    target_agent_id: UUID,
    target_store_id: UUID,
    reason: str,
) -> None:
    await session.execute(
        text("""
            INSERT INTO raw_sales_reassign_backup
                (raw_sale_id, tenant_id, orig_agent_id, orig_store_id,
                 amount, year, month, client, reason)
            VALUES
                (:raw_sale_id, :tenant_id, :orig_agent_id, :orig_store_id,
                 :amount, :year, :month, :client, :reason)
        """),
        {
            "raw_sale_id": rs.id,
            "tenant_id": tenant_id,
            "orig_agent_id": rs.agent_id,
            "orig_store_id": rs.store_id,
            "amount": rs.amount,
            "year": rs.year,
            "month": rs.month,
            "client": rs.client,
            "reason": reason,
        },
    )
    rs.agent_id = target_agent_id
    rs.store_id = target_store_id


async def _upsert_decision(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    year: int,
    month: int,
    client: str,
    amount: Decimal,
    target_agent_id: UUID,
    target_store_id: UUID,
    source: str,
) -> None:
    await session.execute(
        text("""
            INSERT INTO facturi_bonus_decisions
                (tenant_id, year, month, client, amount,
                 target_agent_id, target_store_id, source)
            VALUES
                (:tenant_id, :year, :month, :client, :amount,
                 :target_agent_id, :target_store_id, :source)
            ON CONFLICT (tenant_id, year, month, client, amount)
            DO UPDATE SET
                target_agent_id = EXCLUDED.target_agent_id,
                target_store_id = EXCLUDED.target_store_id,
                source = EXCLUDED.source,
                decided_at = now()
        """),
        {
            "tenant_id": tenant_id,
            "year": year,
            "month": month,
            "client": client,
            "amount": amount,
            "target_agent_id": target_agent_id,
            "target_store_id": target_store_id,
            "source": source,
        },
    )


async def get_facturi_bonus_pending_count(
    session: AsyncSession, tenant_id: UUID,
) -> dict:
    """Versiune lightweight pentru polling — doar count + amount, fără rows/joins."""
    stmt = select(
        RawSale.year, RawSale.month, RawSale.client, RawSale.amount,
    ).where(
        RawSale.tenant_id == tenant_id,
        _facturi_bonus_filter(),
    )
    rows = (await session.execute(stmt)).all()
    decisions = await _load_decisions_map(session, tenant_id)

    pending_count = 0
    pending_amount = Decimal("0")
    for year, month, client, amount in rows:
        chain = _chain_of(client or "")
        key = (year, month, client or "", amount)
        decision = decisions.get(key)
        if chain is None and decision is None:
            continue
        if decision is None:
            pending_count += 1
            pending_amount += amount
    return {"pending_count": pending_count, "pending_amount": pending_amount}


async def list_facturi_bonus_pending(
    session: AsyncSession, tenant_id: UUID,
) -> dict:
    """Returnează toate facturile sub threshold: pending (roșu) + assigned (verde)."""
    target_agent = await _resolve_target_agent(session, tenant_id)
    centrala = await _resolve_centrala_stores(session, tenant_id)
    decisions = await _load_decisions_map(session, tenant_id)

    stmt = (
        select(RawSale, Agent, Store)
        .outerjoin(Agent, Agent.id == RawSale.agent_id)
        .outerjoin(Store, Store.id == RawSale.store_id)
        .where(
            RawSale.tenant_id == tenant_id,
            _facturi_bonus_filter(),
        )
        .order_by(RawSale.amount.asc())
    )
    res = (await session.execute(stmt)).all()

    # Cache pentru store/agent target din decizii (pot diferi de default).
    target_store_ids = {
        d.target_store_id for d in decisions.values() if d.target_store_id is not None
    }
    target_agent_ids = {
        d.target_agent_id for d in decisions.values() if d.target_agent_id is not None
    }
    extra_stores: dict[UUID, Store] = {}
    extra_agents: dict[UUID, Agent] = {}
    if target_store_ids:
        for s in (await session.execute(
            select(Store).where(Store.id.in_(target_store_ids))
        )).scalars().all():
            extra_stores[s.id] = s
    if target_agent_ids:
        for a in (await session.execute(
            select(Agent).where(Agent.id.in_(target_agent_ids))
        )).scalars().all():
            extra_agents[a.id] = a

    rows: list[dict] = []
    pending_count = 0
    pending_amount = Decimal("0")
    assigned_count = 0
    assigned_amount = Decimal("0")

    for raw_sale, agent, store in res:
        chain = _chain_of(raw_sale.client or "")
        key = (raw_sale.year, raw_sale.month, raw_sale.client or "", raw_sale.amount)
        decision = decisions.get(key)

        # Dacă nu e KA și nu are decizie, sar (nu ne interesează).
        if chain is None and decision is None:
            continue

        default_store = centrala.get(chain) if chain else None
        default_agent = target_agent

        if decision is not None:
            sug_store_id = decision.target_store_id
            sug_agent_id = decision.target_agent_id
            sug_store_name = (
                extra_stores[sug_store_id].name
                if sug_store_id and sug_store_id in extra_stores
                else (default_store.name if default_store else None)
            )
            sug_agent_name = (
                extra_agents[sug_agent_id].full_name
                if sug_agent_id and sug_agent_id in extra_agents
                else (default_agent.full_name if default_agent else _TARGET_AGENT_NAME)
            )
            status = "assigned"
            decided_at = decision.decided_at
            decision_source = decision.source
            assigned_count += 1
            assigned_amount += raw_sale.amount
        else:
            sug_store_id = default_store.id if default_store else None
            sug_store_name = default_store.name if default_store else None
            sug_agent_id = default_agent.id if default_agent else None
            sug_agent_name = default_agent.full_name if default_agent else _TARGET_AGENT_NAME
            status = "pending"
            decided_at = None
            decision_source = None
            pending_count += 1
            pending_amount += raw_sale.amount

        rows.append({
            "id": raw_sale.id,
            "year": raw_sale.year,
            "month": raw_sale.month,
            "amount": raw_sale.amount,
            "client": raw_sale.client,
            "chain": chain,
            "agent_id": raw_sale.agent_id,
            "agent_name": agent.full_name if agent else None,
            "store_id": raw_sale.store_id,
            "store_name": store.name if store else None,
            "suggested_store_id": sug_store_id,
            "suggested_store_name": sug_store_name,
            "suggested_agent_id": sug_agent_id,
            "suggested_agent_name": sug_agent_name,
            "status": status,
            "decided_at": decided_at,
            "decision_source": decision_source,
        })

    return {
        "rows": rows,
        "pending_count": pending_count,
        "pending_amount": pending_amount,
        "assigned_count": assigned_count,
        "assigned_amount": assigned_amount,
        "threshold": FACTURI_BONUS_THRESHOLD,
    }


async def apply_facturi_bonus_rule_all(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    reason: str = "auto_rule_on_import",
) -> dict:
    """Auto-apply: pentru toate raw_sales < threshold:
      1. Dacă există decizie persistentă (tenant, year, month, client, amount)
         → aplică target-ul din decizie (indiferent dacă e KA sau nu).
      2. Altfel, dacă clientul matchează pattern KA cunoscut → aplică regula
         automată (Puscuta + CHAIN Centrala) + scrie decizie (source='auto').
      3. Altfel → lasă rândul pending.
    Idempotent — rândurile deja pe target corect se sar peste. Nu face commit.
    """
    target_agent = await _resolve_target_agent(session, tenant_id)
    centrala = await _resolve_centrala_stores(session, tenant_id)
    decisions = await _load_decisions_map(session, tenant_id)

    stmt = select(RawSale).where(
        RawSale.tenant_id == tenant_id,
        _facturi_bonus_filter(),
    )
    rows = (await session.execute(stmt)).scalars().all()

    accepted = 0
    skipped = 0
    for rs in rows:
        key = (rs.year, rs.month, rs.client or "", rs.amount)
        decision = decisions.get(key)

        if decision is not None and decision.target_agent_id and decision.target_store_id:
            if rs.agent_id != decision.target_agent_id or rs.store_id != decision.target_store_id:
                await _backup_and_reassign(
                    session, rs=rs, tenant_id=tenant_id,
                    target_agent_id=decision.target_agent_id,
                    target_store_id=decision.target_store_id,
                    reason=reason,
                )
                accepted += 1
            continue

        if target_agent is None:
            skipped += 1
            continue
        chain = _chain_of(rs.client or "")
        if chain is None:
            skipped += 1
            continue
        suggested = centrala.get(chain)
        if suggested is None:
            skipped += 1
            continue
        if rs.agent_id != target_agent.id or rs.store_id != suggested.id:
            await _backup_and_reassign(
                session, rs=rs, tenant_id=tenant_id,
                target_agent_id=target_agent.id,
                target_store_id=suggested.id,
                reason=reason,
            )
        await _upsert_decision(
            session, tenant_id=tenant_id,
            year=rs.year, month=rs.month,
            client=rs.client or "", amount=rs.amount,
            target_agent_id=target_agent.id,
            target_store_id=suggested.id,
            source="auto",
        )
        accepted += 1
    return {"accepted": accepted, "skipped": skipped}


async def accept_facturi_bonus(
    session: AsyncSession,
    tenant_id: UUID,
    ids: list[UUID],
) -> dict:
    """Manual: user bifează X facturi și apasă "Aplică reasignarea".
    Reasignează pe (Puscuta + CHAIN Centrala) și persistă decizia.
    """
    if not ids:
        return {"accepted": 0, "skipped": 0}

    target_agent = await _resolve_target_agent(session, tenant_id)
    centrala = await _resolve_centrala_stores(session, tenant_id)
    if target_agent is None:
        return {"accepted": 0, "skipped": len(ids)}

    stmt = select(RawSale).where(
        RawSale.tenant_id == tenant_id,
        RawSale.id.in_(ids),
        _facturi_bonus_filter(),
    )
    rows = (await session.execute(stmt)).scalars().all()

    accepted = 0
    skipped = 0
    for rs in rows:
        chain = _chain_of(rs.client or "")
        suggested = centrala.get(chain) if chain else None
        if suggested is None:
            skipped += 1
            continue
        if rs.agent_id != target_agent.id or rs.store_id != suggested.id:
            await _backup_and_reassign(
                session, rs=rs, tenant_id=tenant_id,
                target_agent_id=target_agent.id,
                target_store_id=suggested.id,
                reason=_REASSIGN_REASON,
            )
        await _upsert_decision(
            session, tenant_id=tenant_id,
            year=rs.year, month=rs.month,
            client=rs.client or "", amount=rs.amount,
            target_agent_id=target_agent.id,
            target_store_id=suggested.id,
            source="manual",
        )
        accepted += 1
    skipped += len(ids) - len(rows)
    return {"accepted": accepted, "skipped": skipped}


async def unassign_facturi_bonus(
    session: AsyncSession,
    tenant_id: UUID,
    ids: list[UUID],
) -> dict:
    """Anulează decizia: restaurează agent/store-ul original din backup și
    șterge rândul din facturi_bonus_decisions. Factura redevine "pending".
    """
    if not ids:
        return {"unassigned": 0, "skipped": 0}

    stmt = select(RawSale).where(
        RawSale.tenant_id == tenant_id,
        RawSale.id.in_(ids),
    )
    raws = (await session.execute(stmt)).scalars().all()

    unassigned = 0
    for rs in raws:
        backup = (await session.execute(
            text("""
                SELECT orig_agent_id, orig_store_id
                FROM raw_sales_reassign_backup
                WHERE raw_sale_id = :rid
                ORDER BY reassigned_at DESC
                LIMIT 1
            """),
            {"rid": rs.id},
        )).first()
        if backup is not None:
            rs.agent_id = backup.orig_agent_id
            rs.store_id = backup.orig_store_id
        await session.execute(
            text("""
                DELETE FROM facturi_bonus_decisions
                WHERE tenant_id = :tenant_id
                  AND year = :year AND month = :month
                  AND client = :client AND amount = :amount
            """),
            {
                "tenant_id": tenant_id,
                "year": rs.year,
                "month": rs.month,
                "client": rs.client or "",
                "amount": rs.amount,
            },
        )
        unassigned += 1
    skipped = len(ids) - len(raws)
    return {"unassigned": unassigned, "skipped": skipped}
