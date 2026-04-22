"""Import price_grid + price_grid_meta din legacy adeplast_ka.db și sika_ka.db.

Rulare:
  docker cp .../adeplast_ka.db adeplast-saas-backend-1:/tmp/legacy_adp_ka.db
  docker cp .../sika_ka.db    adeplast-saas-backend-1:/tmp/legacy_sika_ka.db
  docker exec adeplast-saas-backend-1 python scripts/import_legacy_pricing.py
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

import asyncpg

TENANT_ID = os.environ.get("TENANT_ID", "e6cd4519-a2b7-448c-b488-3597a70d3bc3")

# Legacy DB → company
LEGACY_DBS = {
    "adeplast": "/tmp/legacy_adp_ka.db",
    "sika":     "/tmp/legacy_sika_ka.db",
}


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def _parse_ts(v):
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(v).replace(" ", "T"))
    except Exception:
        return datetime.utcnow()


async def import_one(conn, db_path: str, company: str):
    if not Path(db_path).exists():
        print(f"[{company}] SKIP — {db_path} nu există")
        return
    s = sqlite3.connect(db_path)
    s.row_factory = sqlite3.Row

    # Clear
    await conn.execute(
        "DELETE FROM price_grid WHERE tenant_id=$1::uuid AND company=$2",
        TENANT_ID, company,
    )
    await conn.execute(
        "DELETE FROM price_grid_meta WHERE tenant_id=$1::uuid AND company=$2",
        TENANT_ID, company,
    )

    # price_grid
    rows = s.execute(
        "SELECT id, store, row_idx, row_num, group_label, brand_data, "
        "imported_at, import_source FROM price_grid"
    ).fetchall()
    vals = []
    for r in rows:
        try:
            bd = json.loads(r["brand_data"] or "{}")
        except Exception:
            bd = {}
        vals.append((
            uuid.uuid4(),
            uuid.UUID(TENANT_ID),
            company,
            r["store"],
            int(r["row_idx"]),
            r["row_num"],
            r["group_label"],
            json.dumps(bd),
            r["import_source"] or "excel",
            _parse_ts(r["imported_at"]),
            int(r["id"]),
        ))
    if vals:
        await conn.executemany(
            """INSERT INTO price_grid (id, tenant_id, company, store, row_idx,
               row_num, group_label, brand_data, import_source, imported_at, legacy_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11)""",
            vals,
        )
    print(f"[{company}] price_grid: {len(vals)} rânduri importate")

    # price_grid_meta
    meta_rows = s.execute(
        "SELECT store, date_prices, brands, imported_at, imported_by FROM price_grid_meta"
    ).fetchall()
    mvals = []
    for r in meta_rows:
        try:
            brands = json.loads(r["brands"] or "[]")
        except Exception:
            brands = []
        mvals.append((
            uuid.UUID(TENANT_ID),
            company,
            r["store"],
            r["date_prices"],
            json.dumps(brands),
            r["imported_by"],
            _parse_ts(r["imported_at"]),
        ))
    if mvals:
        await conn.executemany(
            """INSERT INTO price_grid_meta (tenant_id, company, store,
               date_prices, brands, imported_by, imported_at)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)""",
            mvals,
        )
    print(f"[{company}] price_grid_meta: {len(mvals)} rânduri importate")
    s.close()


async def main():
    conn = await asyncpg.connect(_pg_dsn())
    try:
        for company, path in LEGACY_DBS.items():
            await import_one(conn, path, company)
        print("[done]")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
