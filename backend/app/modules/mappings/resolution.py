"""
Helpers comuni pentru rezolvare (agent, store) canonic via SAM.

Problema: `raw_sales.agent_id` poate fi NULL (când import-ul nu găsește
asignare), iar `raw_sales.store_id` pointează la Store-ul raw (ex. combinat
"CLIENT | SHIP_TO") care NU coincide cu Store-ul canonic (cheie_finala)
referit din `store_agent_mappings.store_id`.

SAM unifică multiple variante de (client_original, ship_to_original) la
aceeași cheie_finala (ex. "ALTEX ROMANIA SRL | BRICO STORE ARAD" și
"BRICOSTORE ROMANIA SA | BRICOSTORE ARAD" devin ambele "ALTEX ARAD").

Flow de rezolvare (în ordinea priorității, per rând):
  1. raw.agent_id dacă e set
  2. SAM match pe client raw ('CLIENT | SHIP_TO' upper/trim) → agent_unificat
  3. SAM/ASA match pe raw.store_id (edge case, rareori)

Pentru store: SAM.store_id e preferat (canonic, cheie_finala); fallback la
raw.store_id.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import AgentStoreAssignment
from app.modules.mappings.models import StoreAgentMapping


def norm_client_key(client: str | None, ship_to: str | None = None) -> str | None:
    """Cheie normalizată pentru match pe SAM: UPPER(TRIM('CLIENT | SHIP_TO')).

    Dacă `ship_to` e dat, formatează din componente separate (mod folosit la
    build-ul map-ului din SAM). Dacă lipsește, presupune că `client` conține
    deja combinatul 'CLIENT | SHIP_TO' (mod folosit pe raw_sales.client /
    raw_orders.client).
    """
    if ship_to is not None:
        if not client or not ship_to:
            return None
        return f"{client.strip().upper()} | {ship_to.strip().upper()}"
    if not client:
        return None
    return client.strip().upper()


async def client_sam_map(
    session: AsyncSession,
    tenant_id: UUID,
) -> dict[str, tuple[UUID | None, UUID | None]]:
    """Lookup: cheie normalizată → (agent_id, canonical_store_id) din SAM.

    Indexează după DOUĂ chei — amândouă pot match raw.client:
      1. `client_original | ship_to_original` (raw, ex. ADP: 'DEDEMAN SRL | SUCEAVA23')
      2. `client_original | cheie_finala`     (canonical, ex. Sika: 'DEDEMAN SRL | DEDEMAN SUCEAVA 23')

    Astfel un rând raw_orders Sika cu `client='DEDEMAN SRL | DEDEMAN SUCEAVA 23'`
    se rezolvă via entry-ul ADP care are `cheie_finala='DEDEMAN SUCEAVA 23'`,
    fără să duplicăm SAM per sursă.
    """
    rows = (await session.execute(
        select(
            StoreAgentMapping.client_original,
            StoreAgentMapping.ship_to_original,
            StoreAgentMapping.cheie_finala,
            StoreAgentMapping.agent_id,
            StoreAgentMapping.store_id,
        ).where(StoreAgentMapping.tenant_id == tenant_id)
    )).all()
    out: dict[str, tuple[UUID | None, UUID | None]] = {}
    for co, sto, cheie, agent_id, store_id in rows:
        ship_key = norm_client_key(co, sto)
        if ship_key:
            out.setdefault(ship_key, (agent_id, store_id))
        cheie_key = norm_client_key(co, cheie)
        if cheie_key:
            out.setdefault(cheie_key, (agent_id, store_id))
    return out


async def store_agent_map(
    session: AsyncSession,
    tenant_id: UUID,
    store_ids: set[UUID],
) -> dict[UUID, UUID]:
    """Fallback store_id (raw) → agent_id via SAM sau AgentStoreAssignment.

    Activ când rezolvarea pe client fail-uiește și raw.store_id coincide
    cu un SAM.store_id sau ASA.store_id (ex. ADP Alocare populată).
    """
    if not store_ids:
        return {}
    out: dict[UUID, UUID] = {}
    rows = (await session.execute(
        select(StoreAgentMapping.store_id, StoreAgentMapping.agent_id)
        .where(
            StoreAgentMapping.tenant_id == tenant_id,
            StoreAgentMapping.store_id.in_(store_ids),
            StoreAgentMapping.agent_id.is_not(None),
        )
    )).all()
    for store_id, agent_id in rows:
        if store_id is not None and store_id not in out:
            out[store_id] = agent_id

    remaining = store_ids - set(out.keys())
    if remaining:
        rows = (await session.execute(
            select(AgentStoreAssignment.store_id, AgentStoreAssignment.agent_id)
            .where(
                AgentStoreAssignment.tenant_id == tenant_id,
                AgentStoreAssignment.store_id.in_(remaining),
            )
        )).all()
        for store_id, agent_id in rows:
            if store_id not in out:
                out[store_id] = agent_id
    return out


def resolve(
    *,
    agent_id: UUID | None,
    store_id: UUID | None,
    client: str | None,
    client_map: dict[str, tuple[UUID | None, UUID | None]],
    store_map: dict[UUID, UUID],
) -> tuple[UUID | None, UUID | None]:
    """Rezolvă (agent, store) canonic pentru un rând raw.

    Returnează `(final_agent_id, final_store_id)`:
      - final_store: SAM.store_id dacă client-ul e în SAM, altfel raw.store_id
      - final_agent: raw.agent_id > SAM.agent_id > store_map[raw.store_id]
    """
    sam_agent: UUID | None = None
    sam_store: UUID | None = None
    key = norm_client_key(client)
    if key is not None:
        hit = client_map.get(key)
        if hit is not None:
            sam_agent, sam_store = hit

    final_store = sam_store if sam_store is not None else store_id

    if agent_id is not None:
        final_agent = agent_id
    elif sam_agent is not None:
        final_agent = sam_agent
    elif store_id is not None:
        final_agent = store_map.get(store_id)
    else:
        final_agent = None
    return final_agent, final_store
