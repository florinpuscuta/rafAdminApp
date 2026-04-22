"""
Import Panouri & Standuri din legacy `adeplast_ka.db` (table `panouri_standuri`).

Rulare:
  docker cp <path>/adeplast_ka.db adeplast-saas-backend-1:/tmp/legacy_ka.db
  docker exec adeplast-saas-backend-1 python scripts/import_legacy_panouri.py /tmp/legacy_ka.db
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
LEGACY_DB = sys.argv[1] if len(sys.argv) > 1 else "/tmp/legacy_ka.db"


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def connect_sqlite():
    if not Path(LEGACY_DB).exists():
        sys.exit(f"Legacy DB not found: {LEGACY_DB}")
    conn = sqlite3.connect(LEGACY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _parse_ts(v):
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(v).replace(" ", "T"))
    except Exception:
        return datetime.utcnow()


async def main():
    print(f"[start] legacy_db={LEGACY_DB} tenant={TENANT_ID}")
    sqlite_conn = connect_sqlite()
    conn = await asyncpg.connect(_pg_dsn())
    try:
        await conn.execute(
            "DELETE FROM panouri_standuri WHERE tenant_id=$1::uuid", TENANT_ID,
        )
        print("[clear] wiped existing panouri_standuri for tenant")

        rows = sqlite_conn.execute(
            "SELECT id, store_name, panel_type, title, width_cm, height_cm, "
            "location_in_store, notes, photo_filename, photo_thumb, agent, "
            "created_by, created_at, updated_at FROM panouri_standuri"
        ).fetchall()
        vals = []
        for r in rows:
            vals.append((
                uuid.uuid4(),
                uuid.UUID(TENANT_ID),
                r["store_name"],
                r["panel_type"] or "panou",
                r["title"],
                r["width_cm"],
                r["height_cm"],
                r["location_in_store"],
                r["notes"],
                r["photo_filename"],
                r["photo_thumb"],
                r["agent"],
                r["created_by"],
                int(r["id"]),
                _parse_ts(r["created_at"]),
                _parse_ts(r["updated_at"]),
            ))
        if vals:
            await conn.executemany(
                """INSERT INTO panouri_standuri
                   (id, tenant_id, store_name, panel_type, title, width_cm, height_cm,
                    location_in_store, notes, photo_filename, photo_thumb, agent,
                    created_by, legacy_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
                vals,
            )
        print(f"[panouri] imported {len(vals)}")
    finally:
        sqlite_conn.close()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
