"""
Public service pentru modulul `stores`. Deține canonicul (Store) și alias-urile
(StoreAlias). NU atinge tabela `raw_sales` — enrichment-ul acesteia se face
din `sales.service` via contract public.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.stores.models import Store, StoreAlias


async def list_stores(session: AsyncSession, tenant_id: UUID) -> list[Store]:
    result = await session.execute(
        select(Store).where(Store.tenant_id == tenant_id).order_by(Store.name)
    )
    return list(result.scalars().all())


async def list_by_chain(
    session: AsyncSession, tenant_id: UUID, chain: str
) -> list[Store]:
    """Caz-insensitive match pe chain."""
    from sqlalchemy import func as _f
    result = await session.execute(
        select(Store).where(
            Store.tenant_id == tenant_id,
            _f.lower(Store.chain) == chain.lower(),
        )
    )
    return list(result.scalars().all())


async def list_chains(session: AsyncSession, tenant_id: UUID) -> list[str]:
    """Lanțurile distincte definite de tenant (exclude None)."""
    result = await session.execute(
        select(Store.chain)
        .where(Store.tenant_id == tenant_id, Store.chain.is_not(None))
        .distinct()
        .order_by(Store.chain)
    )
    return [row[0] for row in result.all()]


def suggest_matches(
    raw_clients: list[str], stores: list[Store], top: int = 3
) -> dict[str, list[tuple[UUID, str, float]]]:
    """
    Pentru fiecare raw_client, returnează top-N stores canonice similare
    (folosind difflib pe nume normalizat). Score între 0 și 1.
    """
    from difflib import SequenceMatcher

    def norm(s: str) -> str:
        return "".join(ch.lower() for ch in s if ch.isalnum() or ch.isspace()).strip()

    store_targets = [(s.id, s.name, norm(s.name)) for s in stores]
    out: dict[str, list[tuple[UUID, str, float]]] = {}
    for raw in raw_clients:
        raw_n = norm(raw)
        scored = [
            (sid, name, SequenceMatcher(None, raw_n, s_norm).ratio())
            for sid, name, s_norm in store_targets
        ]
        scored.sort(key=lambda x: x[2], reverse=True)
        out[raw] = [(sid, name, round(score, 3)) for sid, name, score in scored[:top] if score > 0.3]
    return out


async def get_store(session: AsyncSession, tenant_id: UUID, store_id: UUID) -> Store | None:
    result = await session.execute(
        select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_store(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    chain: str | None = None,
    city: str | None = None,
) -> Store:
    store = Store(tenant_id=tenant_id, name=name, chain=chain, city=city)
    session.add(store)
    await session.flush()
    return store


async def list_aliases(session: AsyncSession, tenant_id: UUID) -> list[StoreAlias]:
    result = await session.execute(
        select(StoreAlias)
        .where(StoreAlias.tenant_id == tenant_id)
        .order_by(StoreAlias.raw_client)
    )
    return list(result.scalars().all())


async def get_alias_by_raw(
    session: AsyncSession, tenant_id: UUID, raw_client: str
) -> StoreAlias | None:
    result = await session.execute(
        select(StoreAlias).where(
            StoreAlias.tenant_id == tenant_id,
            StoreAlias.raw_client == raw_client,
        )
    )
    return result.scalar_one_or_none()


async def create_alias(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    raw_client: str,
    store_id: UUID,
    resolved_by_user_id: UUID | None = None,
) -> StoreAlias:
    alias = StoreAlias(
        tenant_id=tenant_id,
        raw_client=raw_client,
        store_id=store_id,
        resolved_by_user_id=resolved_by_user_id,
    )
    session.add(alias)
    await session.flush()
    return alias


async def resolve_map(
    session: AsyncSession, tenant_id: UUID, raw_clients: list[str]
) -> dict[str, UUID]:
    """Returnează {raw_client: store_id} pentru cei care au alias înregistrat."""
    if not raw_clients:
        return {}
    result = await session.execute(
        select(StoreAlias.raw_client, StoreAlias.store_id).where(
            StoreAlias.tenant_id == tenant_id,
            StoreAlias.raw_client.in_(raw_clients),
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def get_alias_by_id(
    session: AsyncSession, tenant_id: UUID, alias_id: UUID
) -> StoreAlias | None:
    result = await session.execute(
        select(StoreAlias).where(
            StoreAlias.id == alias_id, StoreAlias.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def delete_alias(session: AsyncSession, alias: StoreAlias) -> None:
    await session.delete(alias)
    await session.commit()


async def get_many(
    session: AsyncSession, tenant_id: UUID, store_ids: list[UUID]
) -> dict[UUID, Store]:
    """Hidratare bulk: {id: Store} pentru ID-urile cerute (cele care aparțin tenantului)."""
    if not store_ids:
        return {}
    result = await session.execute(
        select(Store).where(Store.tenant_id == tenant_id, Store.id.in_(store_ids))
    )
    return {s.id: s for s in result.scalars().all()}


async def bulk_set_active(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    store_ids: list[UUID],
    active: bool,
) -> int:
    """Setează `active` pentru magazine multiple. Doar cele din tenant sunt afectate."""
    from sqlalchemy import update

    if not store_ids:
        return 0
    res = await session.execute(
        update(Store)
        .where(Store.tenant_id == tenant_id, Store.id.in_(store_ids))
        .values(active=active)
    )
    return res.rowcount or 0


async def merge_into(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    primary_id: UUID,
    duplicate_ids: list[UUID],
) -> dict[str, int]:
    """
    Mută toate referințele (raw_sales, store_aliases, agent_store_assignments)
    de la `duplicate_ids` la `primary_id`, apoi șterge duplicatele.
    Tranzacție unică — apelantul face commit.
    """
    from sqlalchemy import delete, text, update

    from app.modules.agents.models import AgentStoreAssignment
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

    # Validare: primary + toate duplicates aparțin tenant-ului
    found = await get_many(session, tenant_id, [primary_id] + dup_set)
    if primary_id not in found:
        raise ValueError("primary_not_found")
    missing = [str(d) for d in dup_set if d not in found]
    if missing:
        raise ValueError(f"duplicates_not_found:{','.join(missing)}")

    # 1) raw_sales.store_id → primary
    sales_res = await session.execute(
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.store_id.in_(dup_set))
        .values(store_id=primary_id)
    )
    sales_reassigned = sales_res.rowcount or 0

    # 2) store_aliases.store_id → primary (nicio coliziune: raw_client e unic per tenant)
    alias_res = await session.execute(
        update(StoreAlias)
        .where(StoreAlias.tenant_id == tenant_id, StoreAlias.store_id.in_(dup_set))
        .values(store_id=primary_id)
    )
    aliases_reassigned = alias_res.rowcount or 0

    # 3) agent_store_assignments.store_id → primary, dedup pe (agent, store=primary)
    dedup_res = await session.execute(
        text("""
            DELETE FROM agent_store_assignments d
            USING agent_store_assignments p
            WHERE d.tenant_id = :tid
              AND d.store_id = ANY(:dups)
              AND p.tenant_id = :tid
              AND p.store_id = :primary
              AND p.agent_id = d.agent_id
        """),
        {"tid": tenant_id, "dups": dup_set, "primary": primary_id},
    )
    assignments_deduped = dedup_res.rowcount or 0
    assign_res = await session.execute(
        update(AgentStoreAssignment)
        .where(
            AgentStoreAssignment.tenant_id == tenant_id,
            AgentStoreAssignment.store_id.in_(dup_set),
        )
        .values(store_id=primary_id)
    )
    assignments_reassigned = assign_res.rowcount or 0

    # 4) șterge stores duplicate
    await session.execute(
        delete(Store).where(Store.tenant_id == tenant_id, Store.id.in_(dup_set))
    )

    return {
        "merged_count": len(dup_set),
        "aliases_reassigned": aliases_reassigned,
        "sales_reassigned": sales_reassigned,
        "assignments_reassigned": assignments_reassigned,
        "assignments_deduped": assignments_deduped,
    }
