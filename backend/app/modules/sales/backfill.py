"""
Backfill `store_id` și `agent_id` pe raw_sales pentru tenant.

Trei strategii, rulate secvențial:
  1. Exact match pe store_aliases  (SQL UPDATE ... FROM)
  2. Auto-create stores pentru clienți KA nemapați (chain + city din combined_key)
  3. Fuzzy match agenți — aliasul Alocare poate fi doar last-name ("Puscuta")
     iar raw_sales.agent e full name ("Florin Puscuta"). Strategie:
       - tokenize ambele, lower+strip diacritice
       - dacă orice token din alias e prezent în raw_sales.agent → match
       - creează alias nou `raw_agent = full_name → agent_id`
       - UPDATE rs SET agent_id ...

Idempotent: rulat de mai multe ori nu strică — skip-ul e pe rânduri deja
mapate (agent_id / store_id NOT NULL).
"""
from __future__ import annotations

import logging
import unicodedata
from uuid import UUID

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent, AgentAlias
from app.modules.sales.models import RawSale
from app.modules.stores.models import Store, StoreAlias

logger = logging.getLogger("adeplast.sales.backfill")


def _norm(s: str) -> str:
    """lowercase + strip diacritice + whitespace collapse."""
    if not s:
        return ""
    nkfd = unicodedata.normalize("NFKD", s)
    no_acc = "".join(ch for ch in nkfd if not unicodedata.combining(ch))
    return " ".join(no_acc.lower().split())


def _tokens(s: str) -> set[str]:
    return {t for t in _norm(s).split() if len(t) >= 3}


async def backfill_stores_exact(session: AsyncSession, tenant_id: UUID) -> int:
    """UPDATE raw_sales SET store_id FROM store_aliases JOIN pe raw_client=client."""
    stmt = text("""
        UPDATE raw_sales rs
        SET store_id = sa.store_id
        FROM store_aliases sa
        WHERE sa.tenant_id = rs.tenant_id
          AND sa.raw_client = rs.client
          AND rs.tenant_id = :tid
          AND rs.store_id IS NULL
    """)
    result = await session.execute(stmt, {"tid": str(tenant_id)})
    return result.rowcount or 0


async def autocreate_ka_stores(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    resolved_by_user_id: UUID | None = None,
) -> dict[str, int]:
    """
    Pentru fiecare `raw_sales.client` KA fără alias — creează Store canonic
    (chain + city extras din combined_key "CHAIN | CITY") și StoreAlias.
    Apoi backfill store_id.
    """
    existing_aliases = (await session.execute(
        select(StoreAlias.raw_client).where(StoreAlias.tenant_id == tenant_id)
    )).scalars().all()
    alias_set = set(existing_aliases)

    unmapped_stmt = (
        select(RawSale.client)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.store_id.is_(None),
            func.upper(RawSale.channel) == "KA",
        )
        .group_by(RawSale.client)
    )
    unmapped = (await session.execute(unmapped_stmt)).scalars().all()
    unmapped = [c for c in unmapped if c and c not in alias_set]

    existing_stores = (await session.execute(
        select(Store).where(Store.tenant_id == tenant_id)
    )).scalars().all()
    store_by_name = {s.name: s for s in existing_stores}

    stores_created = 0
    aliases_created = 0
    for combined in unmapped:
        chain, _, city = combined.partition(" | ")
        chain = chain.strip() or combined
        city = city.strip() or None

        store = store_by_name.get(combined)
        if store is None:
            store = Store(
                tenant_id=tenant_id,
                name=combined,
                chain=chain,
                city=city,
            )
            session.add(store)
            await session.flush()
            store_by_name[combined] = store
            stores_created += 1

        alias = StoreAlias(
            tenant_id=tenant_id,
            raw_client=combined,
            store_id=store.id,
            resolved_by_user_id=resolved_by_user_id,
        )
        session.add(alias)
        aliases_created += 1

    await session.flush()

    updated = await backfill_stores_exact(session, tenant_id)
    return {
        "stores_created": stores_created,
        "aliases_created": aliases_created,
        "rows_updated": updated,
    }


async def backfill_agents_via_store(
    session: AsyncSession,
    tenant_id: UUID,
) -> int:
    """
    Sursa de adevăr pentru agenți pe KA = AgentStoreAssignment (din Alocare).
    În raw_sales, câmpul `agent` text e uniform ("Florin Puscuta" = directorul
    KA) — n-are sens să mapăm prin el. Fiecare magazin KA are un agent dedicat
    din Alocare; folosim assignments ca sursă.

    UPDATE rs SET agent_id = asa.agent_id WHERE rs.store_id = asa.store_id
    (doar KA, doar store-uri unde există un singur assignment activ).
    """
    stmt = text("""
        UPDATE raw_sales rs
        SET agent_id = asa.agent_id
        FROM agent_store_assignments asa
        WHERE asa.tenant_id = rs.tenant_id
          AND asa.store_id = rs.store_id
          AND rs.tenant_id = :tid
          AND UPPER(rs.channel) = 'KA'
          AND rs.store_id IS NOT NULL
    """)
    result = await session.execute(stmt, {"tid": str(tenant_id)})
    return result.rowcount or 0


async def backfill_agents_fuzzy(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    resolved_by_user_id: UUID | None = None,
) -> dict[str, int]:
    """
    Fallback fuzzy match — doar dacă assignment-urile nu acoperă totul.
    """
    # Doar KA — agenții din traditional trade (RETAIL) nu ne interesează.
    exact = text("""
        UPDATE raw_sales rs
        SET agent_id = aa.agent_id
        FROM agent_aliases aa
        WHERE aa.tenant_id = rs.tenant_id
          AND aa.raw_agent = rs.agent
          AND rs.tenant_id = :tid
          AND rs.agent_id IS NULL
          AND UPPER(rs.channel) = 'KA'
    """)
    exact_rows = (await session.execute(exact, {"tid": str(tenant_id)})).rowcount or 0

    aliases = (await session.execute(
        select(AgentAlias.raw_agent, AgentAlias.agent_id).where(
            AgentAlias.tenant_id == tenant_id
        )
    )).all()
    alias_tokens: list[tuple[set[str], UUID, str]] = [
        (_tokens(raw), agent_id, raw) for raw, agent_id in aliases
    ]

    raw_agents_stmt = (
        select(RawSale.agent)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.agent_id.is_(None),
            RawSale.agent.is_not(None),
            func.upper(RawSale.channel) == "KA",
        )
        .group_by(RawSale.agent)
    )
    raw_agents = [a for a in (await session.execute(raw_agents_stmt)).scalars().all() if a]

    existing_alias_raws = {raw for _, _, raw in alias_tokens}
    new_aliases = 0
    mapped_agents: list[tuple[str, UUID]] = []
    unmatched: list[str] = []

    for full_name in raw_agents:
        if full_name in existing_alias_raws:
            continue
        target = _tokens(full_name)
        if not target:
            unmatched.append(full_name)
            continue

        best: tuple[float, UUID] | None = None
        for alias_tok, agent_id, _alias_raw in alias_tokens:
            if not alias_tok:
                continue
            inter = target & alias_tok
            if not inter:
                continue
            score = len(inter) / len(target | alias_tok)
            if best is None or score > best[0]:
                best = (score, agent_id)

        if best is None:
            unmatched.append(full_name)
            continue

        session.add(AgentAlias(
            tenant_id=tenant_id,
            raw_agent=full_name,
            agent_id=best[1],
            resolved_by_user_id=resolved_by_user_id,
        ))
        mapped_agents.append((full_name, best[1]))
        new_aliases += 1

    await session.flush()

    fuzzy_rows = 0
    if mapped_agents:
        fuzzy_rows = (await session.execute(exact, {"tid": str(tenant_id)})).rowcount or 0

    return {
        "exact_rows_updated": exact_rows,
        "fuzzy_aliases_created": new_aliases,
        "fuzzy_rows_updated": fuzzy_rows,
        "unmatched_agents": len(unmatched),
        "unmatched_sample": unmatched[:20],
    }


async def run_full_backfill(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    resolved_by_user_id: UUID | None = None,
    source: str = "ADP",
) -> dict[str, object]:
    """
    Rulează toate strategiile pentru `source` și commit la final.
    Aceeași sursă-de-adevăr (StoreAgentMapping) — dar cu strategie de match
    diferită pe sursă (vezi mappings_service.backfill_raw_sales).
    """
    from app.modules.mappings import service as mappings_service
    mapping_result = await mappings_service.backfill_raw_sales(
        session, tenant_id, source=source,
    )

    # Fallback pentru KA rows rămase nemapate (fișier de mapare neîncărcat
    # sau acoperire parțială): auto-create canonical store din combined_key.
    stores_auto = await autocreate_ka_stores(
        session, tenant_id, resolved_by_user_id=resolved_by_user_id,
    )
    await session.commit()
    return {
        "mapping_rows_updated": mapping_result["rows_updated"],
        "mapping_by_code": mapping_result.get("rows_by_code"),
        "mapping_by_name": mapping_result.get("rows_by_name"),
        "stores_autocreate": stores_auto,
    }
