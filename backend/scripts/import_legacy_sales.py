"""Import comprehensiv raw_sales + master data din legacy adeplast_ka.db + sika_ka.db.

Creează/populează:
  - agents (unique full_name)
  - stores (unique name = client_ship_to)
  - products (unique code = description, max 100 chars)
  - agent_aliases, store_aliases, product_aliases
  - raw_sales (cu store_id, agent_id, product_id rezolvate)
  - store_agent_mappings (din legacy agent_magazine + agent_assignments_current)

Rulare:
  docker exec -e TENANT_ID=<uuid> adeplast-saas-backend-1 \\
    python scripts/import_legacy_sales.py

Presupune că /tmp/legacy_adp_ka.db și /tmp/legacy_sika_ka.db există (docker cp înainte).
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

LEGACY_DBS = {
    "adeplast": "/tmp/legacy_adp_ka.db",
    "sika":     "/tmp/legacy_sika_ka.db",
}

BATCH_SIZE = 5000


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def _norm(s):
    if s is None:
        return ""
    return str(s).strip()


def _store_name(client: str, ship_to: str) -> str:
    """Name unique per (client, ship_to)."""
    client = _norm(client)
    ship_to = _norm(ship_to)
    if not client and not ship_to:
        return ""
    if not ship_to:
        return client[:255]
    if not client:
        return ship_to[:255]
    return f"{client} - {ship_to}"[:255]


async def _fetch_categories(conn) -> dict:
    """Map legacy category_code → product_categories.id."""
    rows = await conn.fetch("SELECT id, code FROM product_categories")
    return {r["code"]: r["id"] for r in rows}


async def _fetch_brands(conn, tenant_id: uuid.UUID) -> dict:
    rows = await conn.fetch(
        "SELECT id, name FROM brands WHERE tenant_id=$1",
        tenant_id,
    )
    return {r["name"].upper(): r["id"] for r in rows}


def _map_brand(raw_brand: str, brands_map: dict):
    """Legacy brand → brand_id. Fallback la Adeplast."""
    raw = _norm(raw_brand).upper()
    if raw in ("SIKA",):
        return brands_map.get("SIKA")
    if raw in ("M_PRIVATA",):
        return brands_map.get("MARCA PRIVATA")
    return brands_map.get("ADEPLAST")


async def run(conn, tenant_id: uuid.UUID):
    print(f"[start] tenant={tenant_id}")

    # ---------- 0. Cleanup existing raw data ----------
    print("[clean] ștergem raw_sales + batches + aliases existente…")
    await conn.execute("DELETE FROM raw_sales WHERE tenant_id=$1", tenant_id)
    await conn.execute(
        "DELETE FROM import_batches WHERE tenant_id=$1 AND source='legacy-migration'",
        tenant_id,
    )

    # ---------- 1. Collect unique masters din TOATE DB-urile ----------
    all_rows = []  # list of dicts pentru raw_sales
    all_clients = {}  # (client, ship_to) → None
    all_agents = set()
    all_products = {}  # code → (name, brand, category)

    for company, db_path in LEGACY_DBS.items():
        if not Path(db_path).exists():
            print(f"[{company}] SKIP — {db_path} lipsește")
            continue
        s = sqlite3.connect(db_path)
        s.row_factory = sqlite3.Row
        rows = s.execute(
            "SELECT year,month,day,client,channel,product_group,agent,"
            "sales,quantity,product_category,brand,description,ship_to,"
            "no_factura FROM raw_sales"
        ).fetchall()
        print(f"[{company}] {len(rows)} raw_sales rows")
        for r in rows:
            client = _norm(r["client"])
            ship_to = _norm(r["ship_to"])
            agent = _norm(r["agent"])
            desc = _norm(r["description"])
            brand = _norm(r["brand"])
            cat = _norm(r["product_category"])
            # skip empty critical
            if not client or not desc:
                continue
            all_clients[(client, ship_to)] = None
            if agent:
                all_agents.add(agent)
            # product key = description (unique enough)
            pcode = desc[:100]
            if pcode not in all_products:
                all_products[pcode] = (desc[:500], brand, cat)
            all_rows.append({
                "company": company,
                "year": int(r["year"] or 0),
                "month": int(r["month"] or 0),
                "client": client,
                "channel": _norm(r["channel"])[:100],
                "agent": agent,
                "sales": float(r["sales"] or 0),
                "quantity": float(r["quantity"] or 0),
                "category": cat[:100],
                "description": desc,
                "ship_to": ship_to,
                "no_factura": _norm(r["no_factura"]),
                "product_code": pcode,
                "brand_raw": brand,
            })
        s.close()

    print(
        f"[masters] clients={len(all_clients)} agents={len(all_agents)} "
        f"products={len(all_products)} rows={len(all_rows)}"
    )

    # ---------- 2. Upsert stores ----------
    print("[stores] upsert…")
    store_map = {}  # (client, ship_to) → store_id
    for (client, ship_to) in all_clients:
        name = _store_name(client, ship_to)
        if not name:
            continue
        # chain detectabil din prefix (DEDEMAN, MEGA, etc.) — simplu: primele 2-3 cuvinte ale client
        chain = None
        upper = client.upper()
        for ch in ("DEDEMAN", "MEGA", "LEROY", "HORNBACH", "BAUMAX", "ARABESQUE",
                   "AMBIENT", "PRACTIKER", "ALTEX", "MOBEXPERT", "DEPO",
                   "COMBRAT", "OBI", "BAUMAX", "CASA", "MAGAZIN"):
            if ch in upper:
                chain = ch
                break
        row = await conn.fetchrow(
            """INSERT INTO stores (id, tenant_id, name, chain, city, active)
               VALUES ($1, $2, $3, $4, $5, true)
               ON CONFLICT (tenant_id, name) DO UPDATE SET name=EXCLUDED.name
               RETURNING id""",
            uuid.uuid4(), tenant_id, name, chain, ship_to[:100] or None,
        )
        store_map[(client, ship_to)] = row["id"]
    print(f"[stores] {len(store_map)} stores")

    # store_aliases: raw_client = client + "|" + ship_to
    print("[store_aliases] seed…")
    alias_vals = []
    for (client, ship_to), sid in store_map.items():
        raw = f"{client}|{ship_to}" if ship_to else client
        alias_vals.append((uuid.uuid4(), tenant_id, raw[:255], sid))
    await conn.execute(
        "DELETE FROM store_aliases WHERE tenant_id=$1",
        tenant_id,
    )
    if alias_vals:
        await conn.executemany(
            """INSERT INTO store_aliases (id, tenant_id, raw_client, store_id)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (tenant_id, raw_client) DO NOTHING""",
            alias_vals,
        )

    # ---------- 3. Upsert agents ----------
    print("[agents] upsert…")
    agent_map = {}
    for agent_name in all_agents:
        row = await conn.fetchrow(
            """INSERT INTO agents (id, tenant_id, full_name, active)
               VALUES ($1, $2, $3, true)
               ON CONFLICT (tenant_id, full_name) DO UPDATE SET full_name=EXCLUDED.full_name
               RETURNING id""",
            uuid.uuid4(), tenant_id, agent_name[:255],
        )
        agent_map[agent_name] = row["id"]
    print(f"[agents] {len(agent_map)} agents")

    # agent_aliases
    print("[agent_aliases] seed…")
    await conn.execute(
        "DELETE FROM agent_aliases WHERE tenant_id=$1",
        tenant_id,
    )
    avals = [
        (uuid.uuid4(), tenant_id, name[:255], aid)
        for name, aid in agent_map.items()
    ]
    if avals:
        await conn.executemany(
            """INSERT INTO agent_aliases (id, tenant_id, raw_agent, agent_id)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (tenant_id, raw_agent) DO NOTHING""",
            avals,
        )

    # ---------- 4. Upsert products ----------
    print("[products] upsert…")
    cats_map = await _fetch_categories(conn)
    brands_map = await _fetch_brands(conn, tenant_id)

    # Asigură existența brand-urilor standard
    for i, bname in enumerate(("Adeplast", "Sika", "Marca Privata")):
        if bname.upper() not in brands_map:
            row = await conn.fetchrow(
                """INSERT INTO brands (id, tenant_id, name, is_private_label, sort_order)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (tenant_id, name) DO NOTHING
                   RETURNING id""",
                uuid.uuid4(), tenant_id, bname,
                bname == "Marca Privata", i,
            )
            if row:
                brands_map[bname.upper()] = row["id"]
    brands_map = await _fetch_brands(conn, tenant_id)

    product_map = {}  # code → product_id
    pvals = []
    for code, (name, brand_raw, cat_code) in all_products.items():
        brand_id = _map_brand(brand_raw, brands_map)
        cat_id = cats_map.get(cat_code) if cat_code else None
        pid = uuid.uuid4()
        product_map[code] = pid
        pvals.append((
            pid, tenant_id, code, name,
            cat_code[:100] if cat_code else None,
            brand_raw[:100] if brand_raw else None,
            cat_id, brand_id,
        ))

    # Batch insert cu conflict handling
    # Existing products ar putea exista deja (din backfill). Verific:
    existing = await conn.fetch(
        "SELECT code, id FROM products WHERE tenant_id=$1",
        tenant_id,
    )
    existing_codes = {r["code"]: r["id"] for r in existing}

    new_pvals = [v for v in pvals if v[2] not in existing_codes]
    # Update product_map cu cele existente
    for code, pid in existing_codes.items():
        if code in product_map:
            product_map[code] = pid

    if new_pvals:
        for chunk_start in range(0, len(new_pvals), BATCH_SIZE):
            chunk = new_pvals[chunk_start:chunk_start + BATCH_SIZE]
            await conn.executemany(
                """INSERT INTO products (id, tenant_id, code, name, category, brand,
                   category_id, brand_id, active)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8, true)
                   ON CONFLICT (tenant_id, code) DO NOTHING""",
                chunk,
            )
    print(f"[products] {len(product_map)} total ({len(new_pvals)} noi)")

    # product_aliases (identity)
    print("[product_aliases] seed…")
    await conn.execute(
        "DELETE FROM product_aliases WHERE tenant_id=$1",
        tenant_id,
    )
    paliases = [
        (uuid.uuid4(), tenant_id, code[:100], pid)
        for code, pid in product_map.items()
    ]
    for chunk_start in range(0, len(paliases), BATCH_SIZE):
        chunk = paliases[chunk_start:chunk_start + BATCH_SIZE]
        await conn.executemany(
            """INSERT INTO product_aliases (id, tenant_id, raw_code, product_id)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT DO NOTHING""",
            chunk,
        )

    # ---------- 5. Insert raw_sales pe batch-uri (ADP + SIKA separat) ----------
    for company, db_path in LEGACY_DBS.items():
        if not Path(db_path).exists():
            continue
        batch_id = uuid.uuid4()
        company_rows = [r for r in all_rows if r["company"] == company]
        await conn.execute(
            """INSERT INTO import_batches (id, tenant_id, filename, source,
               inserted_rows, skipped_rows)
               VALUES ($1, $2, $3, 'legacy-migration', $4, 0)""",
            batch_id, tenant_id, f"{company}_legacy_raw_sales",
            len(company_rows),
        )

        print(f"[raw_sales/{company}] inserez {len(company_rows)} rows…")
        rs_vals = []
        for r in company_rows:
            store_id = store_map.get((r["client"], r["ship_to"]))
            agent_id = agent_map.get(r["agent"]) if r["agent"] else None
            product_id = product_map.get(r["product_code"])
            rs_vals.append((
                uuid.uuid4(), tenant_id, batch_id,
                r["year"], r["month"],
                r["client"][:255], r["channel"], r["product_code"],
                r["description"][:500], r["category"] or None,
                r["sales"], r["quantity"],
                r["agent"][:255] if r["agent"] else None,
                store_id, agent_id, product_id,
                None,  # client_code
            ))
        for chunk_start in range(0, len(rs_vals), BATCH_SIZE):
            chunk = rs_vals[chunk_start:chunk_start + BATCH_SIZE]
            await conn.executemany(
                """INSERT INTO raw_sales (id, tenant_id, batch_id, year, month,
                   client, channel, product_code, product_name, category_code,
                   amount, quantity, agent, store_id, agent_id, product_id,
                   client_code)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)""",
                chunk,
            )
            sys.stdout.write(f"  [{company}] {chunk_start + len(chunk)}/{len(rs_vals)}\r")
            sys.stdout.flush()
        print(f"[raw_sales/{company}] done {len(rs_vals)} rows")

    # ---------- 6. Import store_agent_mappings din legacy (ADP only) ----------
    print("[store_agent_mappings] import…")
    await conn.execute(
        "DELETE FROM store_agent_mappings WHERE tenant_id=$1",
        tenant_id,
    )
    adp = sqlite3.connect(LEGACY_DBS["adeplast"])
    adp.row_factory = sqlite3.Row
    mapping_rows = adp.execute(
        "SELECT chain, ship_to, client, agent FROM agent_magazine"
    ).fetchall()
    samap_vals = []
    seen = set()
    for r in mapping_rows:
        client = _norm(r["client"])
        ship_to = _norm(r["ship_to"])
        agent = _norm(r["agent"])
        if not client or not ship_to:
            continue
        key = (client, ship_to)
        if key in seen:
            continue
        seen.add(key)
        chain = _norm(r["chain"])
        cheie = f"{client}|{ship_to}"
        samap_vals.append((
            uuid.uuid4(), tenant_id, "magazine",
            client[:255], ship_to[:255], agent[:255] or None,
            None,  # cod_numeric
            cheie[:255], agent[:255] or "",
            store_map.get((client, ship_to)),
            agent_map.get(agent) if agent else None,
        ))
    if samap_vals:
        for chunk_start in range(0, len(samap_vals), BATCH_SIZE):
            chunk = samap_vals[chunk_start:chunk_start + BATCH_SIZE]
            await conn.executemany(
                """INSERT INTO store_agent_mappings (id, tenant_id, source,
                   client_original, ship_to_original, agent_original,
                   cod_numeric, cheie_finala, agent_unificat,
                   store_id, agent_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                   ON CONFLICT DO NOTHING""",
                chunk,
            )
    print(f"[store_agent_mappings] {len(samap_vals)} rows")
    adp.close()

    # ---------- 7. Import radiography_orders → raw_orders ----------
    print("[raw_orders] import radiography_orders…")
    await conn.execute(
        """DELETE FROM raw_orders WHERE tenant_id=$1 AND batch_id IN
           (SELECT id FROM import_batches WHERE tenant_id=$1 AND source='legacy-migration')""",
        tenant_id,
    )
    adp = sqlite3.connect(LEGACY_DBS["adeplast"])
    adp.row_factory = sqlite3.Row
    orders_rows = adp.execute(
        "SELECT report_date, chain, client, nr_comanda, cod_art, descriere, "
        "ship_to, quantity, remaining_qty, amount, remaining_amount, status, "
        "ind, has_ind, delivery_date, document_date FROM radiography_orders"
    ).fetchall()

    batch_id = uuid.uuid4()
    await conn.execute(
        """INSERT INTO import_batches (id, tenant_id, filename, source,
           inserted_rows, skipped_rows)
           VALUES ($1, $2, 'radiography_orders', 'legacy-migration', $3, 0)""",
        batch_id, tenant_id, len(orders_rows),
    )
    ro_vals = []
    for r in orders_rows:
        client = _norm(r["client"])
        if not client:
            continue
        ship_to = _norm(r["ship_to"])
        report_date_s = _norm(r["report_date"])
        try:
            rd = datetime.fromisoformat(report_date_s).date()
        except Exception:
            continue
        ro_vals.append((
            uuid.uuid4(), tenant_id, batch_id, "radiography",
            rd, rd.year, rd.month,
            client[:255], None, ship_to[:255] or None,
            _norm(r["chain"])[:100] or None,
            _norm(r["nr_comanda"])[:100] or None,
            _norm(r["cod_art"])[:100] or None,
            _norm(r["descriere"])[:500] or None,
            None,  # category_code
            _norm(r["status"])[:32] or "UNKNOWN",
            float(r["amount"] or 0),
            float(r["quantity"] or 0),
            float(r["remaining_amount"] or 0),
            float(r["remaining_qty"] or 0),
            _norm(r["delivery_date"])[:20] or None,
            _norm(r["ind"])[:100] or None,
            bool(r["has_ind"]),
            store_map.get((client, ship_to)),
            None, None,  # agent_id, product_id
        ))
    for chunk_start in range(0, len(ro_vals), BATCH_SIZE):
        chunk = ro_vals[chunk_start:chunk_start + BATCH_SIZE]
        await conn.executemany(
            """INSERT INTO raw_orders (id, tenant_id, batch_id, source,
               report_date, year, month, client, client_code, ship_to, chain,
               nr_comanda, product_code, product_name, category_code, status,
               amount, quantity, remaining_amount, remaining_quantity,
               data_livrare, ind, has_ind, store_id, agent_id, product_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,
                       $17,$18,$19,$20,$21,$22,$23,$24,$25,$26)""",
            chunk,
        )
    print(f"[raw_orders] {len(ro_vals)} rows")
    adp.close()

    # ---------- 8. activity_problems din users.db ----------
    users_db = "/tmp/legacy_users.db"
    if Path(users_db).exists():
        print("[activity_problems] import…")
        u = sqlite3.connect(users_db)
        u.row_factory = sqlite3.Row
        cols = [c[1] for c in u.execute("PRAGMA table_info(activity_problems)").fetchall()]
        # Try discover column names
        if cols:
            rows = u.execute("SELECT * FROM activity_problems").fetchall()
            print(f"  columns: {cols}, rows: {len(rows)}")
            await conn.execute(
                "DELETE FROM activity_problems WHERE tenant_id=$1",
                tenant_id,
            )
            ap_vals = []
            for r in rows:
                d = dict(r)
                year = int(d.get("year") or d.get("an") or 0)
                month = int(d.get("month") or d.get("luna") or 0)
                scope = _norm(d.get("scope") or d.get("company") or "adeplast")[:16]
                content = _norm(d.get("content") or d.get("text") or "")
                if year and month and content:
                    ap_vals.append((
                        uuid.uuid4(), tenant_id, scope.lower(),
                        year, month, content,
                        _norm(d.get("updated_by") or "")[:255] or None,
                    ))
            if ap_vals:
                await conn.executemany(
                    """INSERT INTO activity_problems (id, tenant_id, scope,
                       year, month, content, updated_by)
                       VALUES ($1,$2,$3,$4,$5,$6,$7)
                       ON CONFLICT (tenant_id, scope, year, month) DO NOTHING""",
                    ap_vals,
                )
            print(f"[activity_problems] {len(ap_vals)} rows")
        u.close()

    print("[done] migrație completă.")


async def main():
    conn = await asyncpg.connect(_pg_dsn())
    try:
        await run(conn, uuid.UUID(TENANT_ID))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
