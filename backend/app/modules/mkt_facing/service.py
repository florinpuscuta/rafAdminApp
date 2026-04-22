"""
Facing Tracker service — port 1:1 al legacy
`adeplast-dashboard/services/facing_service.py`.

Mapping:
  sqlite3 -> AsyncSession (SQLAlchemy 2.0)
  INTEGER AUTOINCREMENT PK -> UUID
  users.db (shared) -> Postgres per-tenant (tenant_id pe fiecare tabelă)
  cheie_finala (Noemi) -> store.name canonic din SaaS

Sursa magazinelor pentru selector: `store_agent_mappings.cheie_finala` —
echivalentul direct al `unified_store_agent_map.cheie_finala` din legacy.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mappings.models import StoreAgentMapping
from app.modules.mkt_facing.models import (
    FacingBrand,
    FacingChainBrand,
    FacingHistory,
    FacingRaion,
    FacingRaionCompetitor,
    FacingSnapshot,
)


# Rețelele recunoscute oficial (trebuie să se potrivească cu _extract_chain)
DEFAULT_CHAINS: list[str] = ["Dedeman", "Altex", "Leroy Merlin", "Hornbach"]


# Pentru fiecare grup, copilul default (unde migrăm valorile vechi).
_PARENT_DEFAULT_CHILD: dict[str, str] = {
    "Constructii": "Alte decat paleti",
    "Adezivi":     "Adezivi (linie)",
    "Chimice":     "Umede",
}


def _now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Raioane CRUD ────────────────────────────────────────────────────────────

async def get_raioane(session: AsyncSession, tenant_id: UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(
        select(FacingRaion)
        .where(FacingRaion.tenant_id == tenant_id)
        .order_by(FacingRaion.sort_order)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "sort_order": r.sort_order,
            "active": r.active,
            "parent_id": r.parent_id,
        }
        for r in rows
    ]


async def get_raioane_tree(
    session: AsyncSession, tenant_id: UUID,
) -> list[dict[str, Any]]:
    raws = await get_raioane(session, tenant_id)
    groups = [r for r in raws if r.get("parent_id") in (None, 0)]
    children_by_parent: dict[UUID, list[dict[str, Any]]] = {}
    for r in raws:
        pid = r.get("parent_id")
        if pid:
            children_by_parent.setdefault(pid, []).append(r)
    for g in groups:
        g["children"] = sorted(
            children_by_parent.get(g["id"], []),
            key=lambda x: x.get("sort_order") or 0,
        )
    groups.sort(key=lambda x: x.get("sort_order") or 0)
    return groups


async def update_raion(
    session: AsyncSession, tenant_id: UUID, raion_id: UUID, name: str,
) -> None:
    await session.execute(
        update(FacingRaion)
        .where(FacingRaion.tenant_id == tenant_id, FacingRaion.id == raion_id)
        .values(name=name)
    )
    await session.commit()


async def add_raion(
    session: AsyncSession, tenant_id: UUID, name: str,
    parent_id: UUID | None = None,
) -> None:
    mx_stmt = select(func.coalesce(func.max(FacingRaion.sort_order), 0) + 1).where(
        FacingRaion.tenant_id == tenant_id,
    )
    mx = (await session.execute(mx_stmt)).scalar_one()
    session.add(FacingRaion(
        tenant_id=tenant_id, name=name, sort_order=mx, parent_id=parent_id,
    ))
    await session.commit()


async def delete_raion(
    session: AsyncSession, tenant_id: UUID, raion_id: UUID,
) -> None:
    """Șterge raionul + copiii + snapshot-urile atașate."""
    child_ids = [
        r for r in (await session.execute(
            select(FacingRaion.id).where(
                FacingRaion.tenant_id == tenant_id,
                FacingRaion.parent_id == raion_id,
            )
        )).scalars().all()
    ]
    all_ids = [raion_id] + child_ids
    await session.execute(
        delete(FacingSnapshot).where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.raion_id.in_(all_ids),
        )
    )
    await session.execute(
        delete(FacingRaion).where(
            FacingRaion.tenant_id == tenant_id,
            FacingRaion.id.in_(all_ids),
        )
    )
    await session.commit()


# ── Brands CRUD ─────────────────────────────────────────────────────────────

async def get_brands(session: AsyncSession, tenant_id: UUID) -> list[dict[str, Any]]:
    rows = (await session.execute(
        select(FacingBrand)
        .where(FacingBrand.tenant_id == tenant_id)
        .order_by(FacingBrand.sort_order)
    )).scalars().all()
    return [
        {
            "id": b.id,
            "name": b.name,
            "color": b.color,
            "is_own": b.is_own,
            "sort_order": b.sort_order,
            "active": b.active,
        }
        for b in rows
    ]


async def update_brand(
    session: AsyncSession, tenant_id: UUID, brand_id: UUID,
    name: str, color: str | None = None,
) -> None:
    vals: dict[str, Any] = {"name": name}
    if color:
        vals["color"] = color
    await session.execute(
        update(FacingBrand)
        .where(FacingBrand.tenant_id == tenant_id, FacingBrand.id == brand_id)
        .values(**vals)
    )
    await session.commit()


async def add_brand(
    session: AsyncSession, tenant_id: UUID, name: str, color: str = "#888888",
) -> None:
    mx = (await session.execute(
        select(func.coalesce(func.max(FacingBrand.sort_order), 0) + 1)
        .where(FacingBrand.tenant_id == tenant_id)
    )).scalar_one()
    new_id = uuid4()
    session.add(FacingBrand(
        id=new_id, tenant_id=tenant_id, name=name, color=color,
        is_own=False, sort_order=mx, active=True,
    ))
    await session.flush()
    # Brandul nou e bifat implicit în TOATE rețelele default.
    for ch in DEFAULT_CHAINS:
        session.add(FacingChainBrand(
            tenant_id=tenant_id, chain=ch, brand_id=new_id, sort_order=mx,
        ))
    await session.commit()


async def delete_brand(
    session: AsyncSession, tenant_id: UUID, brand_id: UUID,
) -> None:
    await session.execute(
        delete(FacingSnapshot).where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.brand_id == brand_id,
        )
    )
    await session.execute(
        delete(FacingChainBrand).where(
            FacingChainBrand.tenant_id == tenant_id,
            FacingChainBrand.brand_id == brand_id,
        )
    )
    await session.execute(
        delete(FacingBrand).where(
            FacingBrand.tenant_id == tenant_id,
            FacingBrand.id == brand_id,
        )
    )
    await session.commit()


# ── Chain-Brands mapping ─────────────────────────────────────────────────────

async def get_chain_brands(
    session: AsyncSession, tenant_id: UUID,
) -> dict[str, list[UUID]]:
    rows = (await session.execute(
        select(FacingChainBrand.chain, FacingChainBrand.brand_id)
        .where(FacingChainBrand.tenant_id == tenant_id)
        .order_by(FacingChainBrand.chain, FacingChainBrand.sort_order)
    )).all()
    out: dict[str, list[UUID]] = {ch: [] for ch in DEFAULT_CHAINS}
    for ch, bid in rows:
        out.setdefault(ch, []).append(bid)
    return out


async def set_chain_brands(
    session: AsyncSession, tenant_id: UUID,
    chain: str, brand_ids: list[UUID],
) -> None:
    await session.execute(
        delete(FacingChainBrand).where(
            FacingChainBrand.tenant_id == tenant_id,
            FacingChainBrand.chain == chain,
        )
    )
    if brand_ids:
        rows = (await session.execute(
            select(FacingBrand.id, FacingBrand.sort_order)
            .where(
                FacingBrand.tenant_id == tenant_id,
                FacingBrand.id.in_(brand_ids),
            )
        )).all()
        order_map = {r[0]: r[1] for r in rows}
        for bid in brand_ids:
            session.add(FacingChainBrand(
                tenant_id=tenant_id, chain=chain, brand_id=bid,
                sort_order=order_map.get(bid, 0),
            ))
    await session.commit()


async def set_chain_brands_bulk(
    session: AsyncSession, tenant_id: UUID,
    matrix: dict[str, list[UUID]],
) -> None:
    for chain, brand_ids in (matrix or {}).items():
        await set_chain_brands(session, tenant_id, chain, brand_ids)


# ── Store list ───────────────────────────────────────────────────────────────

async def get_stores(session: AsyncSession, tenant_id: UUID) -> list[str]:
    """cheie_finala unice din store_agent_mappings (echivalent cu
    `unified_store_agent_map` din legacy)."""
    rows = (await session.execute(
        select(StoreAgentMapping.cheie_finala)
        .where(
            StoreAgentMapping.tenant_id == tenant_id,
            StoreAgentMapping.cheie_finala.is_not(None),
            StoreAgentMapping.cheie_finala != "",
            ~func.upper(StoreAgentMapping.client_original).like("%PUSKIN%"),
        )
        .distinct()
        .order_by(StoreAgentMapping.cheie_finala)
    )).all()
    return sorted({r[0] for r in rows if r[0]})


# ── Snapshots ────────────────────────────────────────────────────────────────

async def save_snapshot(
    session: AsyncSession, tenant_id: UUID,
    store_name: str, raion_id: UUID, brand_id: UUID,
    luna: str, nr_fete: int, user: str = "",
) -> None:
    """Upsert un snapshot + log în history."""
    now = datetime.utcnow()
    # Upsert: prefer UPDATE; dacă 0 rânduri, INSERT.
    res = await session.execute(
        update(FacingSnapshot)
        .where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.store_name == store_name,
            FacingSnapshot.raion_id == raion_id,
            FacingSnapshot.brand_id == brand_id,
            FacingSnapshot.luna == luna,
        )
        .values(nr_fete=nr_fete, updated_at=now, updated_by=user)
    )
    if (res.rowcount or 0) == 0:
        session.add(FacingSnapshot(
            tenant_id=tenant_id, store_name=store_name,
            raion_id=raion_id, brand_id=brand_id, luna=luna,
            nr_fete=nr_fete, updated_at=now, updated_by=user,
        ))
    session.add(FacingHistory(
        tenant_id=tenant_id, store_name=store_name,
        raion_id=raion_id, brand_id=brand_id, luna=luna,
        nr_fete=nr_fete, action="update", changed_at=now, changed_by=user,
    ))
    await session.commit()


async def save_bulk(
    session: AsyncSession, tenant_id: UUID,
    entries: list[dict[str, Any]], user: str = "",
) -> int:
    """Salvează mai multe snapshots. Anti-dublare: când entries conțin
    raioane-copil, ștergem orice snapshot existent pe raionul-părinte pentru
    aceeași (store, brand, luna).
    """
    now = datetime.utcnow()

    parent_rows = (await session.execute(
        select(FacingRaion.id, FacingRaion.parent_id)
        .where(FacingRaion.tenant_id == tenant_id)
    )).all()
    parent_of = {r[0]: r[1] for r in parent_rows}

    cleanup: set[tuple[str, UUID, str, UUID]] = set()
    for e in entries:
        p = parent_of.get(e["raion_id"])
        if p:
            cleanup.add((e["store_name"], e["brand_id"], e["luna"], p))

    for sn, bid, luna, pid in cleanup:
        row = (await session.execute(
            select(FacingSnapshot.nr_fete)
            .where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == sn,
                FacingSnapshot.raion_id == pid,
                FacingSnapshot.brand_id == bid,
                FacingSnapshot.luna == luna,
            )
        )).scalar_one_or_none()
        if row is not None:
            session.add(FacingHistory(
                tenant_id=tenant_id, store_name=sn,
                raion_id=pid, brand_id=bid, luna=luna,
                nr_fete=row, action="migrate_to_children",
                changed_at=now, changed_by=user,
            ))
            await session.execute(
                delete(FacingSnapshot).where(
                    FacingSnapshot.tenant_id == tenant_id,
                    FacingSnapshot.store_name == sn,
                    FacingSnapshot.raion_id == pid,
                    FacingSnapshot.brand_id == bid,
                    FacingSnapshot.luna == luna,
                )
            )

    for e in entries:
        res = await session.execute(
            update(FacingSnapshot)
            .where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == e["store_name"],
                FacingSnapshot.raion_id == e["raion_id"],
                FacingSnapshot.brand_id == e["brand_id"],
                FacingSnapshot.luna == e["luna"],
            )
            .values(nr_fete=e["nr_fete"], updated_at=now, updated_by=user)
        )
        if (res.rowcount or 0) == 0:
            session.add(FacingSnapshot(
                tenant_id=tenant_id, store_name=e["store_name"],
                raion_id=e["raion_id"], brand_id=e["brand_id"],
                luna=e["luna"], nr_fete=e["nr_fete"],
                updated_at=now, updated_by=user,
            ))
        session.add(FacingHistory(
            tenant_id=tenant_id, store_name=e["store_name"],
            raion_id=e["raion_id"], brand_id=e["brand_id"],
            luna=e["luna"], nr_fete=e["nr_fete"],
            action="update", changed_at=now, changed_by=user,
        ))

    await session.commit()
    return len(entries)


async def migrate_month_to_children(
    session: AsyncSession, tenant_id: UUID,
    luna: str, user: str = "",
) -> tuple[int, list[dict[str, Any]]]:
    """Mută snapshot-urile atașate raioanelor-părinte în copilul-default,
    pentru o lună (port 1:1 din legacy)."""
    now = datetime.utcnow()

    raioane_rows = (await session.execute(
        select(FacingRaion.id, FacingRaion.name, FacingRaion.parent_id)
        .where(FacingRaion.tenant_id == tenant_id)
    )).all()
    by_id = {r[0]: {"id": r[0], "name": r[1], "parent_id": r[2]} for r in raioane_rows}
    name_to_id = {r[1]: r[0] for r in raioane_rows}

    mig_map: dict[UUID, UUID] = {}
    for pname, cname in _PARENT_DEFAULT_CHILD.items():
        pid = name_to_id.get(pname)
        cid = name_to_id.get(cname)
        if pid and cid:
            mig_map[pid] = cid

    if not mig_map:
        return 0, []

    parent_ids = list(mig_map.keys())
    rows = (await session.execute(
        select(
            FacingSnapshot.id, FacingSnapshot.store_name,
            FacingSnapshot.raion_id, FacingSnapshot.brand_id,
            FacingSnapshot.luna, FacingSnapshot.nr_fete,
        )
        .where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.luna == luna,
            FacingSnapshot.raion_id.in_(parent_ids),
        )
    )).all()

    migrated = 0
    details: list[dict[str, Any]] = []
    for r in rows:
        snap_id, store_name, raion_id, brand_id, snap_luna, nr_fete = r
        child_id = mig_map[raion_id]

        existing = (await session.execute(
            select(FacingSnapshot.id, FacingSnapshot.nr_fete)
            .where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == store_name,
                FacingSnapshot.raion_id == child_id,
                FacingSnapshot.brand_id == brand_id,
                FacingSnapshot.luna == luna,
            )
        )).one_or_none()

        if existing:
            new_val = (existing[1] or 0) + (nr_fete or 0)
            await session.execute(
                update(FacingSnapshot)
                .where(FacingSnapshot.id == existing[0])
                .values(nr_fete=new_val, updated_at=now, updated_by=user)
            )
        else:
            session.add(FacingSnapshot(
                tenant_id=tenant_id, store_name=store_name,
                raion_id=child_id, brand_id=brand_id, luna=luna,
                nr_fete=nr_fete or 0, updated_at=now, updated_by=user,
            ))

        await session.execute(
            delete(FacingSnapshot).where(FacingSnapshot.id == snap_id)
        )

        session.add(FacingHistory(
            tenant_id=tenant_id, store_name=store_name,
            raion_id=raion_id, brand_id=brand_id, luna=luna,
            nr_fete=nr_fete or 0,
            action=f"migrate_to_child:{child_id}",
            changed_at=now, changed_by=user,
        ))

        migrated += 1
        details.append({
            "store_name": store_name,
            "from_raion_id": raion_id,
            "to_raion_id": child_id,
            "brand_id": brand_id,
            "nr_fete": nr_fete,
        })

    await session.commit()
    return migrated, details


async def delete_store_snapshots(
    session: AsyncSession, tenant_id: UUID,
    store_name: str, luna: str | None = None, user: str = "",
) -> int:
    now = datetime.utcnow()
    if luna:
        cnt = (await session.execute(
            select(func.count(FacingSnapshot.id))
            .where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == store_name,
                FacingSnapshot.luna == luna,
            )
        )).scalar_one()
        await session.execute(
            delete(FacingSnapshot).where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == store_name,
                FacingSnapshot.luna == luna,
            )
        )
        action = "delete_store_month"
        luna_log = luna
    else:
        cnt = (await session.execute(
            select(func.count(FacingSnapshot.id))
            .where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == store_name,
            )
        )).scalar_one()
        await session.execute(
            delete(FacingSnapshot).where(
                FacingSnapshot.tenant_id == tenant_id,
                FacingSnapshot.store_name == store_name,
            )
        )
        action = "delete_store_all"
        luna_log = ""

    session.add(FacingHistory(
        tenant_id=tenant_id, store_name=store_name,
        raion_id=None, brand_id=None,
        luna=luna_log, nr_fete=0, action=action,
        changed_at=now, changed_by=user,
    ))
    await session.commit()
    return int(cnt or 0)


async def get_snapshots(
    session: AsyncSession, tenant_id: UUID,
    store_name: str | None = None, luna: str | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            FacingSnapshot.id, FacingSnapshot.store_name,
            FacingSnapshot.raion_id, FacingRaion.name.label("raion_name"),
            FacingSnapshot.brand_id, FacingBrand.name.label("brand_name"),
            FacingBrand.color.label("brand_color"),
            FacingSnapshot.luna, FacingSnapshot.nr_fete,
            FacingSnapshot.updated_at, FacingSnapshot.updated_by,
        )
        .join(FacingRaion, FacingRaion.id == FacingSnapshot.raion_id)
        .join(FacingBrand, FacingBrand.id == FacingSnapshot.brand_id)
        .where(FacingSnapshot.tenant_id == tenant_id)
    )
    if store_name:
        stmt = stmt.where(FacingSnapshot.store_name == store_name)
    if luna:
        stmt = stmt.where(FacingSnapshot.luna == luna)
    stmt = stmt.order_by(
        FacingSnapshot.store_name, FacingRaion.sort_order, FacingBrand.sort_order,
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id, "store_name": r.store_name,
            "raion_id": r.raion_id, "raion_name": r.raion_name,
            "brand_id": r.brand_id, "brand_name": r.brand_name,
            "brand_color": r.brand_color,
            "luna": r.luna, "nr_fete": r.nr_fete,
            "updated_at": r.updated_at, "updated_by": r.updated_by,
        }
        for r in rows
    ]


async def get_evolution(
    session: AsyncSession, tenant_id: UUID,
    store_name: str | None = None, raion_id: UUID | None = None,
) -> list[dict[str, Any]]:
    stmt = (
        select(
            FacingSnapshot.luna, FacingSnapshot.store_name,
            FacingRaion.name.label("raion_name"), FacingSnapshot.raion_id,
            FacingBrand.name.label("brand_name"),
            FacingBrand.color.label("brand_color"), FacingSnapshot.brand_id,
            FacingSnapshot.nr_fete,
        )
        .join(FacingRaion, FacingRaion.id == FacingSnapshot.raion_id)
        .join(FacingBrand, FacingBrand.id == FacingSnapshot.brand_id)
        .where(FacingSnapshot.tenant_id == tenant_id)
    )
    if store_name:
        stmt = stmt.where(FacingSnapshot.store_name == store_name)
    if raion_id:
        stmt = stmt.where(FacingSnapshot.raion_id == raion_id)
    stmt = stmt.order_by(
        FacingSnapshot.luna, FacingRaion.sort_order, FacingBrand.sort_order,
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "luna": r.luna, "store_name": r.store_name,
            "raion_name": r.raion_name, "raion_id": r.raion_id,
            "brand_name": r.brand_name, "brand_color": r.brand_color,
            "brand_id": r.brand_id, "nr_fete": r.nr_fete,
        }
        for r in rows
    ]


def _extract_chain(store_name: str | None) -> str:
    if not store_name:
        return "Alte"
    upper = store_name.upper()
    if "DEDEMAN" in upper:
        return "Dedeman"
    if "ALTEX" in upper:
        return "Altex"
    if "LEROY" in upper:
        return "Leroy Merlin"
    if "HORNBACH" in upper:
        return "Hornbach"
    return "Alte"


async def get_dashboard_summary(
    session: AsyncSession, tenant_id: UUID, luna: str | None = None,
) -> dict[str, Any]:
    """Port 1:1 al `get_dashboard_summary` din legacy facing_service.py."""
    if not luna:
        mx = (await session.execute(
            select(func.max(FacingSnapshot.luna))
            .where(FacingSnapshot.tenant_id == tenant_id)
        )).scalar_one_or_none()
        luna = mx if mx else datetime.now().strftime("%Y-%m")

    parts = luna.split("-")
    y, m = int(parts[0]), int(parts[1])
    prev_luna = f"{y-1}-12" if m == 1 else f"{y}-{m-1:02d}"

    # Current month: full detail (store × raion × brand)
    curr_rows = (await session.execute(
        select(
            FacingSnapshot.store_name,
            FacingRaion.id.label("raion_id"),
            FacingRaion.name.label("raion_name"),
            FacingRaion.sort_order.label("raion_order"),
            FacingBrand.id.label("brand_id"),
            FacingBrand.name.label("brand_name"),
            FacingBrand.color.label("brand_color"),
            FacingBrand.sort_order.label("brand_order"),
            FacingSnapshot.nr_fete,
        )
        .join(FacingRaion, FacingRaion.id == FacingSnapshot.raion_id)
        .join(FacingBrand, FacingBrand.id == FacingSnapshot.brand_id)
        .where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.luna == luna,
        )
        .order_by(
            FacingSnapshot.store_name,
            FacingRaion.sort_order,
            FacingBrand.sort_order,
        )
    )).all()

    # Previous month: aggregated per store × brand
    prev_rows = (await session.execute(
        select(
            FacingSnapshot.store_name,
            FacingSnapshot.brand_id,
            func.sum(FacingSnapshot.nr_fete).label("total_fete"),
        )
        .where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.luna == prev_luna,
        )
        .group_by(FacingSnapshot.store_name, FacingSnapshot.brand_id)
    )).all()

    chain_brand_set = {
        ch: set(bids) for ch, bids in
        (await get_chain_brands(session, tenant_id)).items()
    }

    own_rows = (await session.execute(
        select(FacingBrand.id, FacingBrand.is_own)
        .where(FacingBrand.tenant_id == tenant_id)
    )).all()
    own_map = {r[0]: int(bool(r[1])) for r in own_rows}

    # Pentru brand_info lookup (când brand e doar în prev_rows)
    brand_info_rows = (await session.execute(
        select(FacingBrand.id, FacingBrand.name, FacingBrand.color, FacingBrand.sort_order)
        .where(FacingBrand.tenant_id == tenant_id)
    )).all()
    brand_info = {r[0]: {"name": r[1], "color": r[2], "sort_order": r[3]} for r in brand_info_rows}

    chains: dict[str, dict[str, Any]] = {}

    def _init_chain(name: str):
        chains[name] = {
            "chain": name,
            "stores_set": set(),
            "brands": {},
            "stores_dict": {},
        }

    for r in curr_rows:
        chain = _extract_chain(r.store_name)
        if chain not in chains:
            _init_chain(chain)
        c = chains[chain]
        c["stores_set"].add(r.store_name)

        bid = r.brand_id
        if bid not in c["brands"]:
            c["brands"][bid] = {
                "brand_id": bid,
                "brand_name": r.brand_name,
                "brand_color": r.brand_color,
                "sort_order": r.brand_order,
                "total_fete": 0,
                "prev_total": 0,
            }
        c["brands"][bid]["total_fete"] += r.nr_fete or 0

        sn = r.store_name
        sd = c["stores_dict"]
        if sn not in sd:
            # Emit direct camelCase (dict-ul e tipizat ca `dict`, fără APISchema
            # care să facă conversia automată).
            sd[sn] = {"storeName": sn, "raioane": {}}
        rn = r.raion_name
        sd[sn]["raioane"].setdefault(rn, []).append({
            "brandName": r.brand_name,
            "brandColor": r.brand_color,
            "nrFete": r.nr_fete,
        })

    for r in prev_rows:
        chain = _extract_chain(r.store_name)
        if chain not in chains:
            _init_chain(chain)
        c = chains[chain]
        bid = r.brand_id
        if bid not in c["brands"] and bid in brand_info:
            bi = brand_info[bid]
            c["brands"][bid] = {
                "brand_id": bid,
                "brand_name": bi["name"],
                "brand_color": bi["color"],
                "sort_order": bi["sort_order"],
                "total_fete": 0,
                "prev_total": 0,
            }
        if bid in c["brands"]:
            c["brands"][bid]["prev_total"] += int(r.total_fete or 0)

    prev_stores_per_chain: dict[str, set[str]] = {}
    for r in prev_rows:
        chain = _extract_chain(r.store_name)
        prev_stores_per_chain.setdefault(chain, set()).add(r.store_name)

    chain_order = ["Dedeman", "Altex", "Leroy Merlin", "Hornbach", "Alte"]
    chains_out: list[dict[str, Any]] = []
    for chain_name in chain_order:
        if chain_name not in chains:
            continue
        c = chains[chain_name]
        nr_mag = len(c["stores_set"])
        prev_nr_mag = len(prev_stores_per_chain.get(chain_name, set()))

        allowed = chain_brand_set.get(chain_name)
        if allowed is None or not allowed:
            allowed_set = set(c["brands"].keys())
        else:
            allowed_set = set(allowed)

        total_all = sum(
            b["total_fete"] for bid, b in c["brands"].items() if bid in allowed_set
        )
        own_total = sum(
            b["total_fete"] for bid, b in c["brands"].items()
            if bid in allowed_set and own_map.get(bid, 0) == 1
        )

        per_store_pcts: list[float] = []
        name_to_bid = {b["brand_name"]: bid for bid, b in c["brands"].items()}
        for sn, sdata in c["stores_dict"].items():
            store_own = 0
            store_total = 0
            for rn, items in sdata["raioane"].items():
                for it in items:
                    bid = name_to_bid.get(it["brandName"])
                    if bid is None or bid not in allowed_set:
                        continue
                    nf = it["nrFete"] or 0
                    store_total += nf
                    if own_map.get(bid, 0) == 1:
                        store_own += nf
            if store_total > 0:
                per_store_pcts.append(store_own / store_total * 100)
        own_pct_avg = (
            sum(per_store_pcts) / len(per_store_pcts)
        ) if per_store_pcts else 0

        prev_per_store_pcts: list[float] = []
        prev_store_agg: dict[str, dict[str, int]] = {}
        for pr in prev_rows:
            if _extract_chain(pr.store_name) != chain_name:
                continue
            bid = pr.brand_id
            if bid not in allowed_set:
                continue
            psn = pr.store_name
            if psn not in prev_store_agg:
                prev_store_agg[psn] = {"own": 0, "total": 0}
            nf = int(pr.total_fete or 0)
            prev_store_agg[psn]["total"] += nf
            if own_map.get(bid, 0) == 1:
                prev_store_agg[psn]["own"] += nf
        for psn, agg in prev_store_agg.items():
            if agg["total"] > 0:
                prev_per_store_pcts.append(agg["own"] / agg["total"] * 100)
        prev_own_pct_avg = (
            sum(prev_per_store_pcts) / len(prev_per_store_pcts)
        ) if prev_per_store_pcts else 0

        brands_sum: list[dict[str, Any]] = []
        for bid in sorted(
            [bid for bid in c["brands"].keys() if bid in allowed_set],
            key=lambda x: c["brands"][x]["sort_order"],
        ):
            b = c["brands"][bid]
            avg_curr = (b["total_fete"] / nr_mag) if nr_mag else 0
            avg_prev = (b["prev_total"] / prev_nr_mag) if prev_nr_mag else 0
            pct = (b["total_fete"] / total_all * 100) if total_all else 0
            brands_sum.append({
                "brand_id": bid,
                "brand_name": b["brand_name"],
                "brand_color": b["brand_color"],
                "total_fete": int(b["total_fete"]),
                "avg_fete": round(avg_curr, 1),
                "prev_avg_fete": round(avg_prev, 1),
                "delta_avg": round(avg_curr - avg_prev, 1),
                "pct": round(pct, 1),
            })

        chains_out.append({
            "chain": chain_name,
            "nr_magazine": nr_mag,
            "prev_nr_magazine": prev_nr_mag,
            "total_fete_all": int(total_all),
            "avg_fete_all": round(total_all / nr_mag, 1) if nr_mag else 0,
            "own_pct_weighted": round(own_pct_avg, 1),
            "prev_own_pct_weighted": round(prev_own_pct_avg, 1),
            "own_pct_delta": round(own_pct_avg - prev_own_pct_avg, 1),
            "own_total_fete": int(own_total),
            "own_stores_counted": len(per_store_pcts),
            "brands_summary": brands_sum,
            "stores": c["stores_dict"],
        })

    chains_out_visible = [c for c in chains_out if c["nr_magazine"] > 0]
    total_mag = sum(c["nr_magazine"] for c in chains_out_visible)

    # Global DIY header
    global_brand_agg: dict[UUID, dict[str, Any]] = {}
    global_total_all = 0
    global_prev_total_all = 0
    global_own_total = 0
    global_prev_own_total = 0

    for chain_name in chain_order:
        if chain_name not in chains:
            continue
        c = chains[chain_name]
        allowed = chain_brand_set.get(chain_name)
        if allowed is None or not allowed:
            chain_allowed_set = set(c["brands"].keys())
        else:
            chain_allowed_set = set(allowed)
        for bid, b in c["brands"].items():
            if bid not in chain_allowed_set:
                continue
            global_total_all += b["total_fete"]
            global_prev_total_all += b["prev_total"]
            is_own = own_map.get(bid, 0) == 1
            if is_own:
                global_own_total += b["total_fete"]
                global_prev_own_total += b["prev_total"]
            if bid not in global_brand_agg:
                global_brand_agg[bid] = {
                    "brand_id": bid,
                    "brand_name": b["brand_name"],
                    "brand_color": b["brand_color"],
                    "sort_order": b["sort_order"],
                    "is_own": 1 if is_own else 0,
                    "total_fete": 0,
                    "prev_total": 0,
                }
            global_brand_agg[bid]["total_fete"] += b["total_fete"]
            global_brand_agg[bid]["prev_total"] += b["prev_total"]

    global_own_pct = (global_own_total / global_total_all * 100) if global_total_all else 0
    global_prev_own_pct = (global_prev_own_total / global_prev_total_all * 100) if global_prev_total_all else 0

    # Arithmetic global
    store_totals_curr: dict[str, dict[str, Any]] = {}
    for r in curr_rows:
        chain = _extract_chain(r.store_name)
        allowed = chain_brand_set.get(chain)
        if allowed is None or not allowed:
            if chain in chains:
                allowed_set = set(chains[chain]["brands"].keys())
            else:
                allowed_set = set()
        else:
            allowed_set = set(allowed)
        bid = r.brand_id
        if bid not in allowed_set:
            continue
        sn = r.store_name
        if sn not in store_totals_curr:
            store_totals_curr[sn] = {"chain": chain, "total": 0, "brands": {}}
        nf = r.nr_fete or 0
        store_totals_curr[sn]["total"] += nf
        store_totals_curr[sn]["brands"][bid] = (
            store_totals_curr[sn]["brands"].get(bid, 0) + nf
        )

    own_pcts_all_stores: list[float] = []
    comp_pcts_per_brand: dict[UUID, list[float]] = {}
    for sn, sd in store_totals_curr.items():
        tot = sd["total"]
        if tot <= 0:
            continue
        own_in_store = sum(
            sd["brands"].get(bid, 0) for bid in sd["brands"].keys()
            if own_map.get(bid, 0) == 1
        )
        own_pcts_all_stores.append(own_in_store / tot * 100)
        for bid, fete in sd["brands"].items():
            if own_map.get(bid, 0) == 1:
                continue
            comp_pcts_per_brand.setdefault(bid, []).append(fete / tot * 100)
    global_own_pct_arith = (
        sum(own_pcts_all_stores) / len(own_pcts_all_stores)
    ) if own_pcts_all_stores else 0

    store_totals_prev: dict[str, dict[str, Any]] = {}
    for pr in prev_rows:
        chain = _extract_chain(pr.store_name)
        allowed = chain_brand_set.get(chain)
        if allowed is None or not allowed:
            if chain in chains:
                allowed_set = set(chains[chain]["brands"].keys())
            else:
                allowed_set = set()
        else:
            allowed_set = set(allowed)
        bid = pr.brand_id
        if bid not in allowed_set:
            continue
        sn = pr.store_name
        if sn not in store_totals_prev:
            store_totals_prev[sn] = {"chain": chain, "total": 0, "brands": {}}
        nf = int(pr.total_fete or 0)
        store_totals_prev[sn]["total"] += nf
        store_totals_prev[sn]["brands"][bid] = (
            store_totals_prev[sn]["brands"].get(bid, 0) + nf
        )
    prev_own_pcts: list[float] = []
    prev_comp_pcts_per_brand: dict[UUID, list[float]] = {}
    for sn, sd in store_totals_prev.items():
        tot = sd["total"]
        if tot <= 0:
            continue
        own_in_store = sum(
            sd["brands"].get(bid, 0) for bid in sd["brands"].keys()
            if own_map.get(bid, 0) == 1
        )
        prev_own_pcts.append(own_in_store / tot * 100)
        for bid, fete in sd["brands"].items():
            if own_map.get(bid, 0) == 1:
                continue
            prev_comp_pcts_per_brand.setdefault(bid, []).append(fete / tot * 100)
    global_prev_own_pct_arith = (
        sum(prev_own_pcts) / len(prev_own_pcts)
    ) if prev_own_pcts else 0

    competitors_global: list[dict[str, Any]] = []
    for bid, b in global_brand_agg.items():
        if b["is_own"]:
            continue
        pct_w = (b["total_fete"] / global_total_all * 100) if global_total_all else 0
        prev_pct_w = (b["prev_total"] / global_prev_total_all * 100) if global_prev_total_all else 0
        arith_list = comp_pcts_per_brand.get(bid, [])
        pct_a = (sum(arith_list) / len(arith_list)) if arith_list else 0
        prev_arith_list = prev_comp_pcts_per_brand.get(bid, [])
        prev_pct_a = (sum(prev_arith_list) / len(prev_arith_list)) if prev_arith_list else 0
        competitors_global.append({
            "brand_id": bid,
            "brand_name": b["brand_name"],
            "brand_color": b["brand_color"],
            "total_fete": int(b["total_fete"]),
            "pct": round(pct_w, 1),
            "pct_arith": round(pct_a, 1),
            "prev_pct": round(prev_pct_w, 1),
            "prev_pct_arith": round(prev_pct_a, 1),
            "delta_pp": round(pct_w - prev_pct_w, 1),
            "delta_pp_arith": round(pct_a - prev_pct_a, 1),
        })
    competitors_global.sort(key=lambda x: -x["pct"])

    return {
        "luna": luna,
        "prev_luna": prev_luna,
        "chains": chains_out_visible,
        "total_chains": len(chains_out_visible),
        "global_total_fete": int(global_total_all),
        "global_own_total_fete": int(global_own_total),
        "global_own_pct_weighted": round(global_own_pct, 1),
        "global_prev_own_pct_weighted": round(global_prev_own_pct, 1),
        "global_own_pct_delta": round(global_own_pct - global_prev_own_pct, 1),
        "global_own_pct_arith": round(global_own_pct_arith, 1),
        "global_prev_own_pct_arith": round(global_prev_own_pct_arith, 1),
        "global_own_pct_arith_delta": round(
            global_own_pct_arith - global_prev_own_pct_arith, 1,
        ),
        "global_stores_counted_arith": len(own_pcts_all_stores),
        "global_competitors": competitors_global,
        "total_magazine": total_mag,
    }


async def get_available_months(
    session: AsyncSession, tenant_id: UUID,
) -> list[str]:
    rows = (await session.execute(
        select(FacingSnapshot.luna)
        .where(FacingSnapshot.tenant_id == tenant_id)
        .distinct()
        .order_by(FacingSnapshot.luna.desc())
    )).all()
    return [r[0] for r in rows]


# ── Dash Face Tracker: cota-parte per sub-raion, per scope ──────────────────

# Mapping scope → nume brand propriu din facing_brands. Acesta e singurul
# lucru hardcodat — restul (ce concurenți are fiecare brand propriu la fiecare
# sub-raion) vine din matricea `facing_raion_competitors`, editabilă din UI.
_SCOPE_OWN_NAME: dict[str, str] = {
    "adp": "Adeplast",
    "sika": "Sika",
}


# ── Matrice concurențe (CRUD) ───────────────────────────────────────────────

async def get_raion_competitors_matrix(
    session: AsyncSession, tenant_id: UUID,
) -> list[dict[str, Any]]:
    rows = (await session.execute(
        select(
            FacingRaionCompetitor.raion_id,
            FacingRaionCompetitor.own_brand_id,
            FacingRaionCompetitor.competitor_brand_id,
            FacingRaionCompetitor.sort_order,
        )
        .where(FacingRaionCompetitor.tenant_id == tenant_id)
        .order_by(
            FacingRaionCompetitor.own_brand_id,
            FacingRaionCompetitor.raion_id,
            FacingRaionCompetitor.sort_order,
        )
    )).all()
    return [
        {
            "raion_id": r[0],
            "own_brand_id": r[1],
            "competitor_brand_id": r[2],
            "sort_order": r[3] or 0,
        }
        for r in rows
    ]


async def set_raion_competitors_matrix(
    session: AsyncSession, tenant_id: UUID,
    entries: list[dict[str, Any]],
) -> int:
    """Înlocuiește complet matricea pentru tenant. Întoarce numărul de rânduri
    scrise. Orice entry existent în DB care NU apare în `entries` e șters."""
    await session.execute(
        delete(FacingRaionCompetitor)
        .where(FacingRaionCompetitor.tenant_id == tenant_id)
    )
    seen: set[tuple[UUID, UUID, UUID]] = set()
    to_insert: list[dict[str, Any]] = []
    for e in entries:
        rid: UUID = e["raion_id"]
        oid: UUID = e["own_brand_id"]
        cid: UUID = e["competitor_brand_id"]
        if oid == cid:
            continue  # nu concurezi cu tine însuți
        key = (rid, oid, cid)
        if key in seen:
            continue
        seen.add(key)
        to_insert.append({
            "tenant_id": tenant_id,
            "raion_id": rid,
            "own_brand_id": oid,
            "competitor_brand_id": cid,
            "sort_order": int(e.get("sort_order") or 0),
        })
    if to_insert:
        await session.execute(
            FacingRaionCompetitor.__table__.insert(), to_insert,
        )
    await session.commit()
    return len(to_insert)


def _build_raion_share_analysis(
    *,
    scope: str,
    own_brand: dict[str, Any],
    # Set de competitor_brand_id (facing_brand) per raion_id configurate în DB
    competitors_by_raion: dict[UUID, list[dict[str, Any]]],
    raioane_rows: list[Any],
    children_by_parent: dict[UUID, list[Any]],
    agg_rows: list[Any],
) -> dict[str, Any]:
    """Construiește o analiză (own + competitori + Alții excl. exclude_brands)
    din agregatele deja calculate. Brandurile din `exclude_brands` nu apar deloc
    în rezultat — nu sunt nici în bare, nici în "Alții" — fiindcă aparțin unui
    alt scope (ex: Sika nu contează în analiza Adeplast)."""
    own_id: UUID = own_brand["id"]
    own_name: str = own_brand["name"]

    # Sub-raioane relevante = cele care au cel puțin 1 competitor configurat
    relevant_sub_ids = set(competitors_by_raion.keys())

    # Găsim părinții sub care sunt aceste sub-raioane
    sub_to_parent: dict[UUID, UUID] = {}
    for r in raioane_rows:
        if r.parent_id is not None:
            sub_to_parent[r.id] = r.parent_id
    parents_map: dict[UUID, Any] = {r.id: r for r in raioane_rows if r.parent_id is None}
    parent_ids: set[UUID] = {sub_to_parent[rid] for rid in relevant_sub_ids if rid in sub_to_parent}
    parents = [parents_map[pid] for pid in parent_ids if pid in parents_map]
    parents.sort(key=lambda p: p.sort_order)

    # Grupare per raion_id — toate brandurile observate (sumă pe toate rețelele)
    # și per raion_id × chain (rețea client) — pentru breakdown-ul per rețea.
    by_raion_full: dict[UUID, list[dict[str, Any]]] = {}
    by_raion_chain: dict[UUID, dict[str, dict[UUID, dict[str, Any]]]] = {}
    for r in agg_rows:
        chain = _extract_chain(getattr(r, "store_name", None))
        cell = {
            "brand_id": r.brand_id,
            "brand_name": r.brand_name,
            "brand_color": r.brand_color,
            "brand_order": r.brand_order,
            "is_own": bool(r.is_own),
            "total_fete": int(r.total_fete or 0),
        }
        bucket = by_raion_chain.setdefault(r.raion_id, {}).setdefault(chain, {})
        prev = bucket.get(r.brand_id)
        if prev is None:
            bucket[r.brand_id] = dict(cell)
        else:
            prev["total_fete"] += cell["total_fete"]

    for rid, chains in by_raion_chain.items():
        totals: dict[UUID, dict[str, Any]] = {}
        for _chain, brand_map in chains.items():
            for bid, cell in brand_map.items():
                prev = totals.get(bid)
                if prev is None:
                    totals[bid] = dict(cell)
                else:
                    prev["total_fete"] += cell["total_fete"]
        by_raion_full[rid] = list(totals.values())

    def _build_sub(sub_raion: Any) -> dict[str, Any]:
        # Competitori configurați pentru acest (own, raion)
        configured = competitors_by_raion.get(sub_raion.id, [])
        competitor_ids = [c["brand_id"] for c in configured]
        competitor_order_map = {c["brand_id"]: c.get("sort_order", 0) for c in configured}
        # brand info pentru configuratorii care nu au fețe (pentru a-i afișa 0%)
        configured_info = {c["brand_id"]: c for c in configured}

        # Matricea = sursa de adevăr. Doar own + competitori bifați contează.
        accepted_ids: set[UUID] = {own_id, *competitor_ids}

        all_rows = by_raion_full.get(sub_raion.id, [])
        accepted_rows = [b for b in all_rows if b["brand_id"] in accepted_ids]

        own_fete = sum(b["total_fete"] for b in accepted_rows if b["brand_id"] == own_id)
        total = sum(b["total_fete"] for b in accepted_rows)

        brands_out: list[dict[str, Any]] = []
        # Own primul
        for b in accepted_rows:
            if b["brand_id"] == own_id:
                brands_out.append({
                    "brand_id": b["brand_id"],
                    "brand_name": b["brand_name"],
                    "brand_color": b["brand_color"],
                    "total_fete": b["total_fete"],
                    "pct": (b["total_fete"] / total * 100) if total else 0.0,
                    "category": "own",
                })
        # Competitori în ordinea sort_order, brand_name
        def _comp_key(bid: UUID) -> tuple[int, str]:
            info = configured_info.get(bid, {})
            return (int(info.get("sort_order", 0)), info.get("brand_name", ""))
        for comp_id in sorted(competitor_ids, key=_comp_key):
            found = next((b for b in accepted_rows if b["brand_id"] == comp_id), None)
            if found is not None:
                brands_out.append({
                    "brand_id": found["brand_id"],
                    "brand_name": found["brand_name"],
                    "brand_color": found["brand_color"],
                    "total_fete": found["total_fete"],
                    "pct": (found["total_fete"] / total * 100) if total else 0.0,
                    "category": "competitor",
                })
            else:
                # Configurat dar fără fețe → afișăm 0%
                info = configured_info[comp_id]
                brands_out.append({
                    "brand_id": comp_id,
                    "brand_name": info.get("brand_name", "?"),
                    "brand_color": info.get("brand_color", "#888"),
                    "total_fete": 0,
                    "pct": 0.0,
                    "category": "competitor",
                })

        # Breakdown per rețea client (Dedeman/Altex/Leroy/Hornbach/Alte),
        # reutilizând accepted_ids + configured_info pentru ordine/culori.
        chain_order = ["Dedeman", "Altex", "Leroy Merlin", "Hornbach", "Alte"]
        chains_out: list[dict[str, Any]] = []
        chain_map = by_raion_chain.get(sub_raion.id, {})
        sorted_chains = sorted(
            chain_map.keys(),
            key=lambda c: (chain_order.index(c) if c in chain_order else 99, c),
        )
        for chain in sorted_chains:
            brand_map = chain_map[chain]
            accepted_rows_s = [
                b for bid, b in brand_map.items() if bid in accepted_ids
            ]
            own_fete_s = sum(
                b["total_fete"] for b in accepted_rows_s if b["brand_id"] == own_id
            )
            total_s = sum(b["total_fete"] for b in accepted_rows_s)

            brands_s: list[dict[str, Any]] = []
            for b in accepted_rows_s:
                if b["brand_id"] == own_id:
                    brands_s.append({
                        "brand_id": b["brand_id"],
                        "brand_name": b["brand_name"],
                        "brand_color": b["brand_color"],
                        "total_fete": b["total_fete"],
                        "pct": (b["total_fete"] / total_s * 100) if total_s else 0.0,
                        "category": "own",
                    })
            for comp_id in sorted(competitor_ids, key=_comp_key):
                found = next(
                    (b for b in accepted_rows_s if b["brand_id"] == comp_id), None,
                )
                if found is not None:
                    brands_s.append({
                        "brand_id": found["brand_id"],
                        "brand_name": found["brand_name"],
                        "brand_color": found["brand_color"],
                        "total_fete": found["total_fete"],
                        "pct": (found["total_fete"] / total_s * 100) if total_s else 0.0,
                        "category": "competitor",
                    })
                else:
                    info = configured_info[comp_id]
                    brands_s.append({
                        "brand_id": comp_id,
                        "brand_name": info.get("brand_name", "?"),
                        "brand_color": info.get("brand_color", "#888"),
                        "total_fete": 0,
                        "pct": 0.0,
                        "category": "competitor",
                    })

            chains_out.append({
                "chain": chain,
                "total_fete": total_s,
                "own_fete": own_fete_s,
                "own_pct": (own_fete_s / total_s * 100) if total_s else 0.0,
                "brands": brands_s,
            })

        return {
            "raion_id": sub_raion.id,
            "raion_name": sub_raion.name,
            "total_fete": total,
            "own_fete": own_fete,
            "own_pct": (own_fete / total * 100) if total else 0.0,
            "brands": brands_out,
            "chains": chains_out,
        }

    parent_out: list[dict[str, Any]] = []
    global_total = 0
    global_own = 0
    competitor_names_collected: dict[UUID, str] = {}
    for p in parents:
        subs_raw = [
            c for c in sorted(
                children_by_parent.get(p.id, []),
                key=lambda c: c.sort_order,
            )
            if c.id in relevant_sub_ids
        ]
        subs = [_build_sub(c) for c in subs_raw]
        for s in subs:
            for b in s["brands"]:
                if b["category"] == "competitor" and b["brand_id"] is not None:
                    competitor_names_collected[b["brand_id"]] = b["brand_name"]
        p_total = sum(s["total_fete"] for s in subs)
        p_own = sum(s["own_fete"] for s in subs)
        parent_out.append({
            "parent_id": p.id,
            "parent_name": p.name,
            "total_fete": p_total,
            "own_fete": p_own,
            "own_pct": (p_own / p_total * 100) if p_total else 0.0,
            "sub_raioane": subs,
        })
        global_total += p_total
        global_own += p_own

    return {
        "scope": scope,
        "own_brand_name": own_name,
        "competitor_names": list(competitor_names_collected.values()),
        "parents": parent_out,
        "global_total_fete": global_total,
        "global_own_fete": global_own,
        "global_own_pct": (global_own / global_total * 100) if global_total else 0.0,
    }


async def get_raion_share(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope: str,
    luna: str | None = None,
) -> dict[str, Any]:
    """Cota-parte fețe per sub-raion. Citește matricea `facing_raion_competitors`
    pentru a decide ce concurenți arată pentru fiecare (own_brand, sub_raion).
    Pentru scope=sikadp returnează AMBELE analize (Adeplast + Sika).
    """
    if scope not in {"adp", "sika", "sikadp"}:
        raise ValueError(f"Scope invalid: {scope}")

    # Luna default = cea mai recentă cu date
    if not luna:
        mx = (await session.execute(
            select(func.max(FacingSnapshot.luna))
            .where(FacingSnapshot.tenant_id == tenant_id)
        )).scalar_one_or_none()
        luna = mx if mx else datetime.now().strftime("%Y-%m")

    # Arbore raioane (full)
    raioane_rows = (await session.execute(
        select(FacingRaion)
        .where(FacingRaion.tenant_id == tenant_id, FacingRaion.active.is_(True))
        .order_by(FacingRaion.sort_order)
    )).scalars().all()
    children_by_parent: dict[UUID, list[Any]] = {}
    for r in raioane_rows:
        if r.parent_id is not None:
            children_by_parent.setdefault(r.parent_id, []).append(r)

    # Brandurile proprii pentru scope-urile cerute (după nume)
    target_scopes: list[str] = ["adp", "sika"] if scope == "sikadp" else [scope]
    own_names = [_SCOPE_OWN_NAME[s] for s in target_scopes]
    own_brand_rows = (await session.execute(
        select(FacingBrand)
        .where(
            FacingBrand.tenant_id == tenant_id,
            FacingBrand.name.in_(own_names),
        )
    )).scalars().all()
    own_by_name: dict[str, Any] = {b.name: b for b in own_brand_rows}

    # Citim matricea pentru toate brandurile proprii relevante
    own_ids = [b.id for b in own_brand_rows]
    if not own_ids:
        return {"luna": luna, "requested_scope": scope, "analyses": []}

    matrix_rows = (await session.execute(
        select(
            FacingRaionCompetitor.own_brand_id,
            FacingRaionCompetitor.raion_id,
            FacingRaionCompetitor.competitor_brand_id,
            FacingRaionCompetitor.sort_order,
            FacingBrand.name.label("comp_name"),
            FacingBrand.color.label("comp_color"),
        )
        .join(
            FacingBrand,
            FacingBrand.id == FacingRaionCompetitor.competitor_brand_id,
        )
        .where(
            FacingRaionCompetitor.tenant_id == tenant_id,
            FacingRaionCompetitor.own_brand_id.in_(own_ids),
        )
    )).all()

    # Structură: per own_brand → per raion_id → listă competitori
    by_own: dict[UUID, dict[UUID, list[dict[str, Any]]]] = {
        oid: {} for oid in own_ids
    }
    relevant_sub_ids: set[UUID] = set()
    for r in matrix_rows:
        by_own.setdefault(r.own_brand_id, {}).setdefault(r.raion_id, []).append({
            "brand_id": r.competitor_brand_id,
            "brand_name": r.comp_name,
            "brand_color": r.comp_color,
            "sort_order": r.sort_order or 0,
        })
        relevant_sub_ids.add(r.raion_id)

    if not relevant_sub_ids:
        return {"luna": luna, "requested_scope": scope, "analyses": []}

    # Agregate fețe pentru toate sub-raioanele relevante — per magazin, ca să
    # putem afișa atât suma (sub-raion) cât și breakdown per magazin în UI.
    agg_rows = (await session.execute(
        select(
            FacingSnapshot.raion_id,
            FacingSnapshot.store_name,
            FacingBrand.id.label("brand_id"),
            FacingBrand.name.label("brand_name"),
            FacingBrand.color.label("brand_color"),
            FacingBrand.sort_order.label("brand_order"),
            FacingBrand.is_own.label("is_own"),
            func.sum(FacingSnapshot.nr_fete).label("total_fete"),
        )
        .join(FacingBrand, FacingBrand.id == FacingSnapshot.brand_id)
        .where(
            FacingSnapshot.tenant_id == tenant_id,
            FacingSnapshot.luna == luna,
            FacingSnapshot.raion_id.in_(relevant_sub_ids),
        )
        .group_by(
            FacingSnapshot.raion_id,
            FacingSnapshot.store_name,
            FacingBrand.id,
            FacingBrand.name,
            FacingBrand.color,
            FacingBrand.sort_order,
            FacingBrand.is_own,
        )
    )).all()

    analyses: list[dict[str, Any]] = []
    for s in target_scopes:
        own_name = _SCOPE_OWN_NAME[s]
        own_brand = own_by_name.get(own_name)
        if own_brand is None:
            continue
        competitors_by_raion = by_own.get(own_brand.id, {})
        analyses.append(_build_raion_share_analysis(
            scope=s,
            own_brand={"id": own_brand.id, "name": own_brand.name},
            competitors_by_raion=competitors_by_raion,
            raioane_rows=raioane_rows,
            children_by_parent=children_by_parent,
            agg_rows=agg_rows,
        ))

    return {
        "luna": luna,
        "requested_scope": scope,
        "analyses": analyses,
    }
