from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.evaluare_agenti.models import (
    AgentCompensation,
    AgentMonthInput,
    AgentStoreBonus,
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
            note=note,
        )
        session.add(existing)
    else:
        existing.salariu_fix = salariu_fix
        existing.note = note
    await session.flush()
    return existing


# ───────────────── Readonly lookups pentru matricea lunară ─────────────────

async def _bonus_by_agent(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> dict[UUID, Decimal]:
    bonus_data = await bonusari_service.get_for_sikadp(
        session, tenant_id, year_curr=year, month=month,
    )
    out: dict[UUID, Decimal] = {}
    for agent_row in bonus_data.get("agents", []):
        aid = agent_row.agent_id
        if aid is None:
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
        cost_comb = mi.cost_combustibil_ron if mi else Decimal("0")
        cost_rev = mi.cost_revizii_ron if mi else Decimal("0")
        alte = mi.alte_costuri_ron if mi else Decimal("0")
        total = salariu_fix + bonus_agent + cost_comb + cost_rev + alte + bonus_raion

        out.append({
            "agent_id": agent.id,
            "agent_name": agent.full_name,
            "vanzari": vanzari,
            "salariu_fix": salariu_fix,
            "bonus_agent": bonus_agent,
            "bonus_raion": bonus_raion,
            "cost_combustibil": cost_comb,
            "cost_revizii": cost_rev,
            "alte_costuri": alte,
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
    cost_combustibil: Decimal,
    cost_revizii: Decimal,
    alte_costuri: Decimal,
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
            cost_combustibil_ron=cost_combustibil,
            cost_revizii_ron=cost_revizii,
            alte_costuri_ron=alte_costuri,
            note=note,
        )
        session.add(existing)
    else:
        existing.cost_combustibil_ron = cost_combustibil
        existing.cost_revizii_ron = cost_revizii
        existing.alte_costuri_ron = alte_costuri
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


# ───────────────── Matricea Agenți ─────────────────

async def build_matrix(
    session: AsyncSession, tenant_id: UUID, *, year: int, month: int,
) -> list[dict]:
    """Agregă per agent: vânzări + pachet + costuri lunare directe + bonusări raion."""
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

    bonus_by_agent = await _bonus_by_agent(session, tenant_id, year=year, month=month)
    raion_by_agent = await _raion_bonus_by_agent(session, tenant_id, year=year, month=month)

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
    rows = []
    for r in res.all():
        agent: Agent = r.Agent
        comp: AgentCompensation | None = r.AgentCompensation
        mi: AgentMonthInput | None = r.AgentMonthInput

        vanzari = sales_by_agent.get(agent.id, Decimal("0"))
        bonus_raion = raion_by_agent.get(agent.id, Decimal("0"))
        bonus_agent = bonus_by_agent.get(agent.id, Decimal("0"))

        salariu = comp.salariu_fix if comp else Decimal("0")

        cost_comb = mi.cost_combustibil_ron if mi else Decimal("0")
        cost_rev = mi.cost_revizii_ron if mi else Decimal("0")
        alte = mi.alte_costuri_ron if mi else Decimal("0")

        salariu_total = salariu + bonus_agent
        total_cost = (
            salariu_total + cost_comb + cost_rev + alte + bonus_raion
        )
        cost_per_100k: Decimal | None = None
        if vanzari > 0:
            cost_per_100k = (total_cost / (vanzari / Decimal("100000"))).quantize(
                Decimal("0.01")
            )

        rows.append({
            "agent_id": agent.id,
            "agent_name": agent.full_name,
            "vanzari": vanzari,
            "salariu_fix": salariu,
            "bonus_agent": bonus_agent,
            "salariu_total": salariu_total,
            "cost_combustibil": cost_comb,
            "cost_revizii": cost_rev,
            "alte_costuri": alte,
            "bonus_raion": bonus_raion,
            "total_cost": total_cost,
            "cost_per_100k": cost_per_100k,
        })
    return rows
