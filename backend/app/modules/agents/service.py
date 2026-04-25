"""
Public service pentru modulul `agents`. Deține Agent + AgentAlias.
NU atinge `raw_sales` — enrichment via contract din `sales.service`.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent, AgentAlias


async def list_agents(session: AsyncSession, tenant_id: UUID) -> list[Agent]:
    return await list_agents_by_tenants(session, [tenant_id])


async def list_agents_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[Agent]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(Agent)
        .where(Agent.tenant_id.in_(tenant_ids))
        .order_by(Agent.full_name)
    )
    return list(result.scalars().all())


async def get_agent(session: AsyncSession, tenant_id: UUID, agent_id: UUID) -> Agent | None:
    result = await session.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_agent(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    full_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> Agent:
    agent = Agent(tenant_id=tenant_id, full_name=full_name, email=email, phone=phone)
    session.add(agent)
    await session.flush()
    return agent


async def list_aliases(session: AsyncSession, tenant_id: UUID) -> list[AgentAlias]:
    return await list_aliases_by_tenants(session, [tenant_id])


async def list_aliases_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[AgentAlias]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(AgentAlias)
        .where(AgentAlias.tenant_id.in_(tenant_ids))
        .order_by(AgentAlias.raw_agent)
    )
    return list(result.scalars().all())


async def get_alias_by_raw(
    session: AsyncSession, tenant_id: UUID, raw_agent: str
) -> AgentAlias | None:
    result = await session.execute(
        select(AgentAlias).where(
            AgentAlias.tenant_id == tenant_id,
            AgentAlias.raw_agent == raw_agent,
        )
    )
    return result.scalar_one_or_none()


async def create_alias(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    raw_agent: str,
    agent_id: UUID,
    resolved_by_user_id: UUID | None = None,
) -> AgentAlias:
    alias = AgentAlias(
        tenant_id=tenant_id,
        raw_agent=raw_agent,
        agent_id=agent_id,
        resolved_by_user_id=resolved_by_user_id,
    )
    session.add(alias)
    await session.flush()
    return alias


async def resolve_map(
    session: AsyncSession, tenant_id: UUID, raw_agents: list[str]
) -> dict[str, UUID]:
    if not raw_agents:
        return {}
    result = await session.execute(
        select(AgentAlias.raw_agent, AgentAlias.agent_id).where(
            AgentAlias.tenant_id == tenant_id,
            AgentAlias.raw_agent.in_(raw_agents),
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def get_alias_by_id(
    session: AsyncSession, tenant_id: UUID, alias_id: UUID
) -> AgentAlias | None:
    result = await session.execute(
        select(AgentAlias).where(
            AgentAlias.id == alias_id, AgentAlias.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def delete_alias(session: AsyncSession, alias: AgentAlias) -> None:
    await session.delete(alias)
    await session.commit()


async def get_many(
    session: AsyncSession, tenant_id: UUID, agent_ids: list[UUID]
) -> dict[UUID, Agent]:
    if not agent_ids:
        return {}
    result = await session.execute(
        select(Agent).where(Agent.tenant_id == tenant_id, Agent.id.in_(agent_ids))
    )
    return {a.id: a for a in result.scalars().all()}


async def bulk_set_active(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    agent_ids: list[UUID],
    active: bool,
) -> int:
    from sqlalchemy import update

    if not agent_ids:
        return 0
    res = await session.execute(
        update(Agent)
        .where(Agent.tenant_id == tenant_id, Agent.id.in_(agent_ids))
        .values(active=active)
    )
    return res.rowcount or 0


# ── Agent-Store Assignments ──────────────────────────────────────────────
from app.modules.agents.models import AgentStoreAssignment  # noqa: E402


async def list_assignments(
    session: AsyncSession, tenant_id: UUID
) -> list[AgentStoreAssignment]:
    return await list_assignments_by_tenants(session, [tenant_id])


async def list_assignments_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[AgentStoreAssignment]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(AgentStoreAssignment)
        .where(AgentStoreAssignment.tenant_id.in_(tenant_ids))
    )
    return list(result.scalars().all())


async def assign_store_to_agent(
    session: AsyncSession, *, tenant_id: UUID, agent_id: UUID, store_id: UUID
) -> AgentStoreAssignment:
    """Assigns (idempotent) — dacă există deja, returnăm existenta."""
    existing = await session.execute(
        select(AgentStoreAssignment).where(
            AgentStoreAssignment.tenant_id == tenant_id,
            AgentStoreAssignment.agent_id == agent_id,
            AgentStoreAssignment.store_id == store_id,
        )
    )
    a = existing.scalar_one_or_none()
    if a is not None:
        return a
    a = AgentStoreAssignment(tenant_id=tenant_id, agent_id=agent_id, store_id=store_id)
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


async def unassign_store_from_agent(
    session: AsyncSession, *, tenant_id: UUID, agent_id: UUID, store_id: UUID
) -> bool:
    result = await session.execute(
        select(AgentStoreAssignment).where(
            AgentStoreAssignment.tenant_id == tenant_id,
            AgentStoreAssignment.agent_id == agent_id,
            AgentStoreAssignment.store_id == store_id,
        )
    )
    a = result.scalar_one_or_none()
    if a is None:
        return False
    await session.delete(a)
    await session.commit()
    return True


async def merge_into(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    primary_id: UUID,
    duplicate_ids: list[UUID],
) -> dict[str, int]:
    """
    Mută raw_sales + agent_aliases + agent_store_assignments de la duplicate
    la primary, apoi șterge duplicate. Apelantul face commit.
    """
    from sqlalchemy import delete, text, update

    from app.modules.sales.models import RawSale

    dup_set = [d for d in duplicate_ids if d != primary_id]
    if not dup_set:
        return {
            "merged_count": 0,
            "aliases_reassigned": 0,
            "sales_reassigned": 0,
            "assignments_reassigned": 0,
            "assignments_deduped": 0,
        }

    found = await get_many(session, tenant_id, [primary_id] + dup_set)
    if primary_id not in found:
        raise ValueError("primary_not_found")
    missing = [str(d) for d in dup_set if d not in found]
    if missing:
        raise ValueError(f"duplicates_not_found:{','.join(missing)}")

    sales_res = await session.execute(
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.agent_id.in_(dup_set))
        .values(agent_id=primary_id)
    )
    sales_reassigned = sales_res.rowcount or 0

    alias_res = await session.execute(
        update(AgentAlias)
        .where(AgentAlias.tenant_id == tenant_id, AgentAlias.agent_id.in_(dup_set))
        .values(agent_id=primary_id)
    )
    aliases_reassigned = alias_res.rowcount or 0

    dedup_res = await session.execute(
        text("""
            DELETE FROM agent_store_assignments d
            USING agent_store_assignments p
            WHERE d.tenant_id = :tid
              AND d.agent_id = ANY(:dups)
              AND p.tenant_id = :tid
              AND p.agent_id = :primary
              AND p.store_id = d.store_id
        """),
        {"tid": tenant_id, "dups": dup_set, "primary": primary_id},
    )
    assignments_deduped = dedup_res.rowcount or 0
    assign_res = await session.execute(
        update(AgentStoreAssignment)
        .where(
            AgentStoreAssignment.tenant_id == tenant_id,
            AgentStoreAssignment.agent_id.in_(dup_set),
        )
        .values(agent_id=primary_id)
    )
    assignments_reassigned = assign_res.rowcount or 0

    await session.execute(
        delete(Agent).where(Agent.tenant_id == tenant_id, Agent.id.in_(dup_set))
    )

    return {
        "merged_count": len(dup_set),
        "aliases_reassigned": aliases_reassigned,
        "sales_reassigned": sales_reassigned,
        "assignments_reassigned": assignments_reassigned,
        "assignments_deduped": assignments_deduped,
    }
