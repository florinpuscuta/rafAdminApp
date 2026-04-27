"""Seed `store_aliases` + `store_agent_mappings` din Noemi master mapping.

Acelasi mecanism ca `_normalize_alocare` din ADP, dar alimentat dintr-un xlsx
master (Noemi) care acoperă ambele surse: ADP + SIKA. Idempotent — re-rulabil
oricând Noemi face update-uri.

Pentru fiecare tenant target (adeplast / sika):
  1. Asigură Store cu name=cheie_finala pentru fiecare cheie unică.
  2. Creează StoreAlias `(client_orig | ship_orig)` → store_canonic.
  3. Asigură Agent canonic per `agent_unificat` + AgentAlias `agent_orig`.
  4. Populează SAM `(source, client_orig, ship_orig, cod_numeric, agent_orig)`
     → store_canonic + agent_canonic. Pentru cod_numeric multiplu (CSV),
     creează un rând per cod.
  5. Re-resolve raw_sales.store_id prin alias (UPDATE bulk via raw_client).
  6. List/delete Store-uri orphan (fără raw_sales și fără Noemi mapping).

Usage:
  docker exec -w /app adeplast-saas-backend-1 python -m scripts.seed_noemi_mapping --dry-run
  docker exec -w /app adeplast-saas-backend-1 python -m scripts.seed_noemi_mapping --apply
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import openpyxl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings


XLSX_PATH = Path(__file__).resolve().parent.parent / "seed_data" / "noemi_store_mappings.xlsx"

CHAINS = {
    "DEDEMAN": "Dedeman",
    "ALTEX": "Altex",
    "BRICOSTORE": "Altex",
    "BRICO STORE": "Altex",
    "LEROY": "Leroy Merlin",
    "MERLIN": "Leroy Merlin",
    "HORNBACH": "Hornbach",
}

SOURCE_TO_SLUG = {"ADP": "adeplast", "SIKA": "sika"}

# Cheie_finala-uri excluse — entități care nu sunt magazine reale (sediu firmă,
# centrale, parteneri non-retail). Vânzările pe aceste rânduri rămân fără
# Store mapping (raw_sales.store_id rămâne NULL după resolve).
EXCLUDED_KEYS_UPPER = {"PUSKIN SOL & CO S.R.L."}


def detect_chain(name: str | None) -> str | None:
    if not name:
        return None
    upper = name.upper()
    for kw, chain in CHAINS.items():
        if kw in upper:
            return chain
    return None


def parse_codes(raw: Any) -> list[str]:
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    return [c.strip() for c in re.split(r"[,;\s]+", s) if c.strip()]


def load_noemi() -> list[dict[str, Any]]:
    if not XLSX_PATH.exists():
        sys.exit(f"Missing: {XLSX_PATH}")
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb["Mapare Magazine"]
    out: list[dict[str, Any]] = []
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r or not r[0]:
            continue
        source, client, ship, codes, agent_orig, _vanz, cheie, agent_unif = r
        if not (source and client and ship and cheie and agent_unif):
            continue
        if str(cheie).strip().upper() in EXCLUDED_KEYS_UPPER:
            continue
        out.append({
            "source": str(source).strip().upper(),
            "client_original": str(client).strip(),
            "ship_to_original": str(ship).strip(),
            "codes": parse_codes(codes),
            "agent_original": str(agent_orig).strip() if agent_orig else None,
            "cheie_finala": str(cheie).strip(),
            "agent_unificat": str(agent_unif).strip(),
        })
    return out


async def get_tenant_id(session: AsyncSession, slug: str) -> UUID | None:
    row = (await session.execute(
        text("SELECT id FROM organizations WHERE slug = :s"),
        {"s": slug},
    )).first()
    return row[0] if row else None


async def seed_tenant(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    slug: str,
    rows: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    """Seed Noemi mapping for one tenant. Returns stats dict."""

    stats = defaultdict(int)
    actions: list[str] = []

    # ── 1. Asigur Store-uri canonice (one per cheie_finala) ──────────────
    canonic_keys = {r["cheie_finala"] for r in rows}
    existing_stores = {
        name: sid for name, sid in (await session.execute(
            text("SELECT name, id FROM stores WHERE tenant_id = :t"),
            {"t": tenant_id},
        )).all()
    }

    canonic_id: dict[str, UUID] = {}
    for cheie in canonic_keys:
        if cheie in existing_stores:
            canonic_id[cheie] = existing_stores[cheie]
            stats["stores_existing"] += 1
            continue
        chain = detect_chain(cheie) or detect_chain(rows[0]["client_original"])
        new_id = uuid4()
        if not dry_run:
            await session.execute(
                text(
                    "INSERT INTO stores (id, tenant_id, name, chain, city, active, created_at) "
                    "VALUES (:id, :t, :n, :c, :city, true, now())"
                ),
                {"id": new_id, "t": tenant_id, "n": cheie, "c": chain, "city": cheie},
            )
        canonic_id[cheie] = new_id
        actions.append(f"  + Store '{cheie}' (chain={chain})")
        stats["stores_created"] += 1

    # Update map cu cele noi pentru lookups următoare.
    existing_stores.update(canonic_id)

    # ── 2. Asigur Agent-i canonici ──────────────────────────────────────
    agent_names = {r["agent_unificat"] for r in rows if r["agent_unificat"]}
    existing_agents = {
        name: aid for name, aid in (await session.execute(
            text("SELECT full_name, id FROM agents WHERE tenant_id = :t"),
            {"t": tenant_id},
        )).all()
    }
    agent_id: dict[str, UUID] = {}
    for full_name in agent_names:
        if full_name in existing_agents:
            agent_id[full_name] = existing_agents[full_name]
            stats["agents_existing"] += 1
            continue
        new_id = uuid4()
        if not dry_run:
            await session.execute(
                text(
                    "INSERT INTO agents (id, tenant_id, full_name, active, created_at) "
                    "VALUES (:id, :t, :n, true, now())"
                ),
                {"id": new_id, "t": tenant_id, "n": full_name},
            )
        agent_id[full_name] = new_id
        actions.append(f"  + Agent '{full_name}'")
        stats["agents_created"] += 1

    # ── 3. Asigur StoreAlias `(client_orig | ship_orig) → canonic` ──────
    existing_aliases = {
        raw: sid for raw, sid in (await session.execute(
            text("SELECT raw_client, store_id FROM store_aliases WHERE tenant_id = :t"),
            {"t": tenant_id},
        )).all()
    }

    for r in rows:
        combined = f"{r['client_original']} | {r['ship_to_original']}"
        target = canonic_id[r["cheie_finala"]]
        existing = existing_aliases.get(combined)
        if existing == target:
            stats["aliases_unchanged"] += 1
            continue
        if existing is None:
            if not dry_run:
                await session.execute(
                    text(
                        "INSERT INTO store_aliases (id, tenant_id, raw_client, store_id, "
                        "resolved_by_user_id) "
                        "VALUES (gen_random_uuid(), :t, :raw, :sid, NULL)"
                    ),
                    {"t": tenant_id, "raw": combined, "sid": target},
                )
            stats["aliases_created"] += 1
        else:
            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE store_aliases SET store_id = :sid "
                        "WHERE tenant_id = :t AND raw_client = :raw"
                    ),
                    {"t": tenant_id, "raw": combined, "sid": target},
                )
            actions.append(f"  ~ Alias '{combined}' redirected → {r['cheie_finala']}")
            stats["aliases_redirected"] += 1
        existing_aliases[combined] = target

    # ── 4. Asigur AgentAlias `(agent_orig) → agent_canonic` ─────────────
    existing_agent_aliases = {
        raw: aid for raw, aid in (await session.execute(
            text("SELECT raw_agent, agent_id FROM agent_aliases WHERE tenant_id = :t"),
            {"t": tenant_id},
        )).all()
    }
    seen_agent_pairs: set[tuple[str, str]] = set()
    for r in rows:
        ao = r.get("agent_original")
        if not ao:
            continue
        au = r["agent_unificat"]
        key = (ao, au)
        if key in seen_agent_pairs:
            continue
        seen_agent_pairs.add(key)
        target = agent_id[au]
        existing = existing_agent_aliases.get(ao)
        if existing == target:
            stats["agent_aliases_unchanged"] += 1
            continue
        if existing is None:
            if not dry_run:
                await session.execute(
                    text(
                        "INSERT INTO agent_aliases (id, tenant_id, raw_agent, agent_id, "
                        "resolved_by_user_id) "
                        "VALUES (gen_random_uuid(), :t, :raw, :aid, NULL)"
                    ),
                    {"t": tenant_id, "raw": ao, "aid": target},
                )
            stats["agent_aliases_created"] += 1
        else:
            if not dry_run:
                await session.execute(
                    text(
                        "UPDATE agent_aliases SET agent_id = :aid "
                        "WHERE tenant_id = :t AND raw_agent = :raw"
                    ),
                    {"t": tenant_id, "raw": ao, "aid": target},
                )
            actions.append(f"  ~ AgentAlias '{ao}' redirected → {au}")
            stats["agent_aliases_redirected"] += 1
        existing_agent_aliases[ao] = target

    # ── 5. SAM: (source, client_orig, ship_orig) cu cod_numeric per row ─
    # Unique constraint: (tenant, source, client_original, ship_to_original).
    # Pentru cod_numeric multiplu, păstrăm primul cod în `cod_numeric` și
    # nu duplicăm rândul (constraint-ul nu permite). Restul codurilor pot fi
    # adăugate ca alias-uri suplimentare în viitor dacă e nevoie.
    existing_sam = {
        (src, cli, ship): sid for src, cli, ship, sid in (await session.execute(
            text(
                "SELECT source, client_original, ship_to_original, store_id "
                "FROM store_agent_mappings WHERE tenant_id = :t"
            ),
            {"t": tenant_id},
        )).all()
    }
    for r in rows:
        src = r["source"]  # ADP / SIKA
        cli = r["client_original"]
        ship = r["ship_to_original"]
        sid = canonic_id[r["cheie_finala"]]
        aid = agent_id[r["agent_unificat"]]
        cod = r["codes"][0] if r["codes"] else None
        cheie = r["cheie_finala"]
        au = r["agent_unificat"]
        key = (src, cli, ship)
        if key in existing_sam:
            if existing_sam[key] != sid:
                if not dry_run:
                    await session.execute(
                        text(
                            "UPDATE store_agent_mappings SET store_id=:sid, agent_id=:aid, "
                            "cod_numeric=:cod, cheie_finala=:cheie, agent_unificat=:au, updated_at=now() "
                            "WHERE tenant_id=:t AND source=:src AND client_original=:cli "
                            "AND ship_to_original=:ship"
                        ),
                        {
                            "t": tenant_id, "src": src, "cli": cli, "ship": ship,
                            "sid": sid, "aid": aid, "cod": cod,
                            "cheie": cheie, "au": au,
                        },
                    )
                actions.append(f"  ~ SAM ({src}, {cli}, {ship}) redirected → {cheie}")
                stats["sam_redirected"] += 1
            else:
                stats["sam_unchanged"] += 1
            continue
        if not dry_run:
            await session.execute(
                text(
                    "INSERT INTO store_agent_mappings ("
                    "id, tenant_id, source, client_original, ship_to_original, "
                    "agent_original, cod_numeric, cheie_finala, agent_unificat, "
                    "store_id, agent_id, created_at, updated_at) "
                    "VALUES (gen_random_uuid(), :t, :src, :cli, :ship, :ao, :cod, "
                    ":cheie, :au, :sid, :aid, now(), now())"
                ),
                {
                    "t": tenant_id, "src": src, "cli": cli, "ship": ship,
                    "ao": r.get("agent_original"), "cod": cod,
                    "cheie": cheie, "au": au, "sid": sid, "aid": aid,
                },
            )
        stats["sam_created"] += 1

    # ── 6. Re-resolve raw_sales prin alias-urile noi ────────────────────
    # UPDATE raw_sales SET store_id = canonic WHERE client = combined_key
    # Aplicăm doar pentru rândurile care au store_id != canonic (sau NULL).
    redirected = 0
    if not dry_run:
        result = await session.execute(
            text(
                "UPDATE raw_sales rs SET store_id = sa.store_id "
                "FROM store_aliases sa "
                "WHERE rs.tenant_id = :t AND sa.tenant_id = :t "
                "AND rs.client = sa.raw_client "
                "AND (rs.store_id IS NULL OR rs.store_id <> sa.store_id)"
            ),
            {"t": tenant_id},
        )
        redirected = result.rowcount or 0
    else:
        result = await session.execute(
            text(
                "SELECT COUNT(*) FROM raw_sales rs "
                "JOIN store_aliases sa ON sa.tenant_id = rs.tenant_id "
                "AND sa.raw_client = rs.client "
                "WHERE rs.tenant_id = :t "
                "AND (rs.store_id IS NULL OR rs.store_id <> sa.store_id)"
            ),
            {"t": tenant_id},
        )
        redirected = result.scalar() or 0
    stats["raw_sales_redirected"] = redirected

    # ── 7. Identifică Store-uri orphan ──────────────────────────────────
    # Definiție orphan: Store care NU e canonic (nu apare ca cheie_finala în Noemi)
    # ȘI fără raw_sales rămase după redirect-ul prin alias.
    # store_aliases vechi (`DEDEMAN SRL | DEDEMAN ARAD 41` → vechi_id) cascade-ează
    # prin FK ON DELETE CASCADE când ștergem Store-ul vechi.
    canonic_ids_list = list(canonic_id.values())
    if dry_run:
        # Simulăm UPDATE-ul: raw_sales redirectate ies din count.
        orphan_query = text(
            "SELECT s.id, s.name FROM stores s "
            "WHERE s.tenant_id = :t "
            "AND s.id <> ALL(:canonic_ids) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM raw_sales rs WHERE rs.store_id = s.id "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM store_aliases sa "
            "    WHERE sa.tenant_id = rs.tenant_id AND sa.raw_client = rs.client"
            "  )"
            ") "
            "AND NOT EXISTS (SELECT 1 FROM raw_orders ro WHERE ro.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM agent_visits av WHERE av.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM agent_store_bonus asb WHERE asb.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM store_contact_bonus scb WHERE scb.store_id = s.id) "
            "ORDER BY s.name"
        )
    else:
        orphan_query = text(
            "SELECT s.id, s.name FROM stores s "
            "WHERE s.tenant_id = :t "
            "AND s.id <> ALL(:canonic_ids) "
            "AND NOT EXISTS (SELECT 1 FROM raw_sales rs WHERE rs.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM raw_orders ro WHERE ro.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM agent_visits av WHERE av.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM agent_store_bonus asb WHERE asb.store_id = s.id) "
            "AND NOT EXISTS (SELECT 1 FROM store_contact_bonus scb WHERE scb.store_id = s.id) "
            "ORDER BY s.name"
        )
    orphans = (await session.execute(
        orphan_query, {"t": tenant_id, "canonic_ids": canonic_ids_list},
    )).all()

    stats["stores_orphan"] = len(orphans)
    if orphans:
        actions.append(f"  Orphan stores ({len(orphans)}):")
        for sid, name in orphans[:20]:
            actions.append(f"    - {name}")
        if len(orphans) > 20:
            actions.append(f"    ... +{len(orphans) - 20} more")

    if not dry_run and orphans:
        ids = [sid for sid, _ in orphans]
        await session.execute(
            text("DELETE FROM stores WHERE tenant_id = :t AND id = ANY(:ids)"),
            {"t": tenant_id, "ids": ids},
        )
        stats["stores_deleted"] = len(ids)

    return {"stats": dict(stats), "actions": actions}


async def main(dry_run: bool, tenants_filter: list[str]) -> int:
    rows = load_noemi()
    print(f"Noemi xlsx: {len(rows)} rows loaded from {XLSX_PATH.name}")
    print(f"  unique cheie_finala: {len({r['cheie_finala'] for r in rows})}")
    print(f"  per source: " + ", ".join(
        f"{src}={sum(1 for r in rows if r['source']==src)}"
        for src in sorted({r['source'] for r in rows})
    ))
    print(f"  unique agents: {len({r['agent_unificat'] for r in rows})}")
    print()

    # Group rows by tenant slug
    by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        slug = SOURCE_TO_SLUG.get(r["source"])
        if not slug:
            continue
        if tenants_filter and slug not in tenants_filter:
            continue
        by_slug[slug].append(r)

    engine = create_async_engine(settings.database_url)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    overall: dict[str, Any] = {}
    async with SessionFactory() as session:
        for slug, tenant_rows in sorted(by_slug.items()):
            tenant_id = await get_tenant_id(session, slug)
            if not tenant_id:
                print(f"⚠️  Tenant '{slug}' nu există — skip.")
                continue
            mode = "DRY-RUN" if dry_run else "APPLY"
            print(f"━━━ Tenant: {slug} (id={tenant_id}) [{mode}] ━━━")
            print(f"  Noemi rows targeted: {len(tenant_rows)}")

            result = await seed_tenant(
                session,
                tenant_id=tenant_id,
                slug=slug,
                rows=tenant_rows,
                dry_run=dry_run,
            )
            overall[slug] = result

            print(f"  Stats:")
            for k, v in sorted(result["stats"].items()):
                print(f"    {k:35s} {v}")
            if result["actions"]:
                print(f"  Actions ({len(result['actions'])} lines):")
                for a in result["actions"][:60]:
                    print(a)
                if len(result["actions"]) > 60:
                    print(f"    ... +{len(result['actions']) - 60} more lines")
            print()

        if not dry_run:
            await session.commit()
            print("✅ Committed.")
        else:
            await session.rollback()
            print("ℹ️  Dry-run — no changes committed.")

    await engine.dispose()
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="Print plan, no changes")
    g.add_argument("--apply", action="store_true", help="Execute the seed")
    p.add_argument("--tenants", nargs="*", default=None,
                   help="Restrict to tenants (slug). Default: all from Noemi.")
    args = p.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run, tenants_filter=args.tenants or [])))
