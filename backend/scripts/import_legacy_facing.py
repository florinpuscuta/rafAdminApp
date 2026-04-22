"""
Import Facing Tracker din legacy `users.db` (adeplast-dashboard).

Rulare:
  docker cp <path>/users.db adeplast-saas-backend-1:/tmp/legacy_users.db
  docker exec -e LEGACY_USERS_DB=/tmp/legacy_users.db \\
    adeplast-saas-backend-1 python scripts/import_legacy_facing.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

import asyncpg

TENANT_ID = os.environ.get("TENANT_ID", "e6cd4519-a2b7-448c-b488-3597a70d3bc3")
# Path-ul pot fi dat via `python scripts/import_legacy_facing.py /tmp/users.db`
LEGACY_DB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/legacy_users.db"


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    # asyncpg accepts postgresql://; strip SQLAlchemy driver suffix
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def connect_sqlite():
    if not Path(LEGACY_DB).exists():
        sys.exit(f"Legacy DB not found: {LEGACY_DB}")
    conn = sqlite3.connect(LEGACY_DB)
    conn.row_factory = sqlite3.Row
    return conn


async def clear_existing(conn):
    # Șterge DOAR snapshots/history/chain_brands — păstrăm raioane și brands
    # cu UUID-urile lor existente (matricea `facing_raion_competitors` și
    # alte configurări de tenant au FK la ele; dacă le-am recrea cu noi
    # UUID-uri, cascade ON DELETE ne-ar șterge configurările de fiecare sync).
    await conn.execute(
        "DELETE FROM facing_snapshots WHERE tenant_id=$1::uuid", TENANT_ID,
    )
    await conn.execute(
        "DELETE FROM facing_history WHERE tenant_id=$1::uuid", TENANT_ID,
    )
    await conn.execute(
        "DELETE FROM facing_chain_brands WHERE tenant_id=$1::uuid", TENANT_ID,
    )
    print("[clear] wiped snapshots/history/chain_brands (kept raioane+brands)")


async def import_raioane(sqlite_conn, conn):
    """Upsert raioane după nume — păstrează UUID-urile existente."""
    rows = sqlite_conn.execute(
        "SELECT id, name, sort_order, COALESCE(active,1) AS active, parent_id "
        "FROM facing_raioane ORDER BY parent_id NULLS FIRST, id"
    ).fetchall()
    # Încarcă raioane existente → nume → UUID
    existing = await conn.fetch(
        "SELECT id, name FROM facing_raioane WHERE tenant_id=$1::uuid",
        TENANT_ID,
    )
    name_to_uuid: dict[str, uuid.UUID] = {r["name"]: r["id"] for r in existing}

    id_map: dict[int, uuid.UUID] = {}
    legacy_names: set[str] = set()
    for r in rows:
        nm = r["name"]
        legacy_names.add(nm)
        if nm in name_to_uuid:
            id_map[int(r["id"])] = name_to_uuid[nm]
        else:
            id_map[int(r["id"])] = uuid.uuid4()

    # Pas 1: INSERT sau UPDATE (metadata + parent_id)
    for r in rows:
        nid = id_map[int(r["id"])]
        parent = r["parent_id"]
        parent_uuid = id_map.get(int(parent)) if parent else None
        if r["name"] in name_to_uuid:
            await conn.execute(
                """UPDATE facing_raioane
                   SET sort_order=$1, active=$2, parent_id=$3, legacy_id=$4
                   WHERE id=$5""",
                r["sort_order"] or 0, bool(r["active"]),
                parent_uuid, int(r["id"]), nid,
            )
        else:
            await conn.execute(
                """INSERT INTO facing_raioane
                   (id, tenant_id, name, sort_order, active, parent_id, legacy_id)
                   VALUES ($1,$2::uuid,$3,$4,$5,$6,$7)""",
                nid, TENANT_ID, r["name"],
                r["sort_order"] or 0, bool(r["active"]),
                parent_uuid, int(r["id"]),
            )

    # Pas 2: șterge raioane orfan (existente în DB dar nu și în legacy)
    orphan_ids = [
        uid for nm, uid in name_to_uuid.items() if nm not in legacy_names
    ]
    if orphan_ids:
        await conn.execute(
            "DELETE FROM facing_raioane WHERE id = ANY($1::uuid[])",
            orphan_ids,
        )
    print(f"[raioane] upserted {len(rows)} (orphans deleted: {len(orphan_ids)})")
    return id_map


async def import_brands(sqlite_conn, conn):
    """Upsert brands după nume — păstrează UUID-urile existente."""
    rows = sqlite_conn.execute(
        "SELECT id, name, color, COALESCE(is_own,0) AS is_own, "
        "sort_order, COALESCE(active,1) AS active FROM facing_brands ORDER BY id"
    ).fetchall()
    existing = await conn.fetch(
        "SELECT id, name FROM facing_brands WHERE tenant_id=$1::uuid",
        TENANT_ID,
    )
    name_to_uuid: dict[str, uuid.UUID] = {r["name"]: r["id"] for r in existing}

    id_map: dict[int, uuid.UUID] = {}
    legacy_names: set[str] = set()
    for r in rows:
        nm = r["name"]
        legacy_names.add(nm)
        if nm in name_to_uuid:
            id_map[int(r["id"])] = name_to_uuid[nm]
        else:
            id_map[int(r["id"])] = uuid.uuid4()

    for r in rows:
        bid = id_map[int(r["id"])]
        if r["name"] in name_to_uuid:
            await conn.execute(
                """UPDATE facing_brands
                   SET color=$1, is_own=$2, sort_order=$3, active=$4, legacy_id=$5
                   WHERE id=$6""",
                r["color"] or "#888888", bool(r["is_own"]),
                r["sort_order"] or 0, bool(r["active"]),
                int(r["id"]), bid,
            )
        else:
            await conn.execute(
                """INSERT INTO facing_brands
                   (id, tenant_id, name, color, is_own, sort_order, active, legacy_id)
                   VALUES ($1,$2::uuid,$3,$4,$5,$6,$7,$8)""",
                bid, TENANT_ID, r["name"], r["color"] or "#888888",
                bool(r["is_own"]), r["sort_order"] or 0,
                bool(r["active"]), int(r["id"]),
            )

    orphan_ids = [
        uid for nm, uid in name_to_uuid.items() if nm not in legacy_names
    ]
    if orphan_ids:
        await conn.execute(
            "DELETE FROM facing_brands WHERE id = ANY($1::uuid[])",
            orphan_ids,
        )
    print(f"[brands] upserted {len(rows)} (orphans deleted: {len(orphan_ids)})")
    return id_map


async def import_chain_brands(sqlite_conn, conn, brand_map):
    rows = sqlite_conn.execute(
        "SELECT chain, brand_id, sort_order FROM facing_chain_brands"
    ).fetchall()
    vals = []
    for r in rows:
        bid_new = brand_map.get(int(r["brand_id"]))
        if not bid_new:
            continue
        vals.append((uuid.UUID(TENANT_ID), r["chain"], bid_new, r["sort_order"] or 0))
    if vals:
        await conn.executemany(
            """INSERT INTO facing_chain_brands
               (tenant_id, chain, brand_id, sort_order) VALUES ($1,$2,$3,$4)""",
            vals,
        )
    print(f"[chain_brands] imported {len(vals)}/{len(rows)}")


def _parse_ts(v):
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(v).replace(" ", "T"))
    except Exception:
        return datetime.utcnow()


async def import_snapshots(sqlite_conn, conn, raion_map, brand_map):
    rows = sqlite_conn.execute(
        "SELECT store_name, raion_id, brand_id, luna, nr_fete, "
        "updated_at, updated_by FROM facing_snapshots"
    ).fetchall()
    vals = []
    skipped = 0
    for r in rows:
        rid_new = raion_map.get(int(r["raion_id"])) if r["raion_id"] else None
        bid_new = brand_map.get(int(r["brand_id"])) if r["brand_id"] else None
        if not rid_new or not bid_new:
            skipped += 1
            continue
        vals.append((
            uuid.uuid4(),
            uuid.UUID(TENANT_ID),
            r["store_name"],
            rid_new,
            bid_new,
            r["luna"],
            r["nr_fete"] or 0,
            _parse_ts(r["updated_at"]),
            r["updated_by"],
        ))
    if vals:
        await conn.executemany(
            """INSERT INTO facing_snapshots
               (id, tenant_id, store_name, raion_id, brand_id,
                luna, nr_fete, updated_at, updated_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
            vals,
        )
    print(f"[snapshots] imported {len(vals)}, skipped {skipped}")


async def import_history(sqlite_conn, conn, raion_map, brand_map):
    rows = sqlite_conn.execute(
        "SELECT store_name, raion_id, brand_id, luna, nr_fete, "
        "action, changed_at, changed_by FROM facing_history"
    ).fetchall()
    vals = []
    for r in rows:
        legacy_rid = r["raion_id"]
        legacy_bid = r["brand_id"]
        rid_new = raion_map.get(int(legacy_rid)) if legacy_rid else None
        bid_new = brand_map.get(int(legacy_bid)) if legacy_bid else None
        vals.append((
            uuid.uuid4(),
            uuid.UUID(TENANT_ID),
            r["store_name"] or "",
            rid_new,
            bid_new,
            r["luna"] or "",
            r["nr_fete"] or 0,
            r["action"] or "update",
            _parse_ts(r["changed_at"]),
            r["changed_by"],
            int(legacy_rid) if legacy_rid is not None else None,
            int(legacy_bid) if legacy_bid is not None else None,
        ))
    if vals:
        await conn.executemany(
            """INSERT INTO facing_history
               (id, tenant_id, store_name, raion_id, brand_id,
                luna, nr_fete, action, changed_at, changed_by,
                legacy_raion_id, legacy_brand_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
            vals,
        )
    print(f"[history] imported {len(vals)}")


async def main():
    print(f"[start] legacy_db={LEGACY_DB} tenant={TENANT_ID}")
    sqlite_conn = connect_sqlite()
    conn = await asyncpg.connect(_pg_dsn())
    try:
        await clear_existing(conn)
        raion_map = await import_raioane(sqlite_conn, conn)
        brand_map = await import_brands(sqlite_conn, conn)
        await import_chain_brands(sqlite_conn, conn, brand_map)
        await import_snapshots(sqlite_conn, conn, raion_map, brand_map)
        await import_history(sqlite_conn, conn, raion_map, brand_map)
        print("[done] import complete")
    finally:
        sqlite_conn.close()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
