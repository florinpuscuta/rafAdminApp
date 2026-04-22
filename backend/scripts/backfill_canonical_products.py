"""Back-fill canonical Products + ProductAliases + raw_sales.product_id.

Scope:
  1. Seed `product_categories` pentru codurile raw care lipsesc (global).
  2. Per tenant cu date: seed `brands` (Adeplast, Sika, Marca Privata).
  3. Per tenant: inserează câte un `Product` per `product_code` distinct
     din `raw_sales`, cu `category_id` rezolvat prin cod și `brand_id`
     derivat din regulă (Sika dacă batch-ul e sika_*, Marca Privata dacă
     numele e în `M_PRIVATA_DESCS`, altfel Adeplast).
  4. Seed `product_aliases` (identity map: raw_code = product.code).
  5. Back-fill `raw_sales.product_id` via aliases.

Totul e idempotent (ON CONFLICT DO NOTHING / UPDATE).

Rulare:
  docker exec adeplast-saas-backend-1 python scripts/backfill_canonical_products.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg

# Permite `from app...` când rulăm scriptul direct.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

from app.modules.prices._m_privata_descs import M_PRIVATA_DESCS


# Categorii raw care nu sunt încă în `product_categories` (globale).
# Format: (code, label, sort_order).
MISSING_CATEGORIES: list[tuple[str, str, int]] = [
    ("DIBLURI", "Dibluri", 21),
    ("DIVERSE", "Diverse", 24),
    ("HOLCIMVRAC", "Holcim Vrac", 30),
    ("MEMBRANE", "Membrane", 31),
    ("PALETI", "Paleți", 32),
    ("EXTRUDAT", "Polistiren Extrudat", 33),
    ("AMB MU", "Ambalaje Mortare", 34),
    ("AMB UMEDE", "Ambalaje Umede", 35),
    ("PLASA", "Plasă", 36),
    ("CONSUMABIL", "Consumabile", 37),
    ("PS SCHIMB", "PS Schimb", 38),
    ("MOTORINA", "Motorină", 39),
    ("PROFILE", "Profile", 40),
    ("S_BURG", "S_BURG", 41),
]


# Clasificarea Sika: pattern-urile din numele produsului → cod categorie
# canonică (MU/EPS/UMEDE/DIBLURI). Primul match câștigă; dacă nimic nu
# matchează, default = UMEDE (sealantz/primeri/lichide — majoritate Sika).
SIKA_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ANCHORFIX|ANCHOR FIX", re.I), "DIBLURI"),
    (re.compile(r"INSULATE.*POLYSTY|POLYSTY.*INSULATE|\bEPS\b|\bXPS\b", re.I), "EPS"),
    (re.compile(
        r"CERAM-?\d|GROUT|TOPSEAL|TOP SEAL|MONOTOP|MONO TOP|WALL-?\d|"
        r"TILEBOND|TILE BOND|SIKAFLOOR.*PRONTO|SIKAWALL|SIKAGROUT|SIKAMONOTOP|"
        r"QUARTZ SAND|SF TS",
        re.I,
    ), "MU"),
]
SIKA_FALLBACK_CAT = "UMEDE"


# Branduri canonice per tenant. Format: (name, is_private_label, sort_order).
TENANT_BRANDS: list[tuple[str, bool, int]] = [
    ("Adeplast", False, 1),
    ("Sika", False, 2),
    ("Marca Privata", True, 10),
]


def _pg_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@db:5432/adeplast_saas",
    )
    return re.sub(r"^postgresql\+\w+://", "postgresql://", dsn)


def _norm(name: str | None) -> str:
    return " ".join((name or "").upper().split())


async def seed_global_categories(conn: asyncpg.Connection) -> None:
    for code, label, sort_order in MISSING_CATEGORIES:
        await conn.execute(
            """
            INSERT INTO product_categories (id, code, label, sort_order, created_at)
            VALUES (gen_random_uuid(), $1, $2, $3, NOW())
            ON CONFLICT (code) DO NOTHING
            """,
            code, label, sort_order,
        )
    print(f"[categories] asigurate {len(MISSING_CATEGORIES)} coduri (idempotent)")


async def seed_brands(conn: asyncpg.Connection, tenant_id) -> dict[str, object]:
    for name, is_pl, sort_order in TENANT_BRANDS:
        await conn.execute(
            """
            INSERT INTO brands (id, tenant_id, name, is_private_label, sort_order, created_at)
            VALUES (gen_random_uuid(), $1, $2, $3, $4, NOW())
            ON CONFLICT ON CONSTRAINT uq_brands_tenant_name DO NOTHING
            """,
            tenant_id, name, is_pl, sort_order,
        )
    rows = await conn.fetch(
        "SELECT id, name FROM brands WHERE tenant_id=$1", tenant_id,
    )
    return {r["name"]: r["id"] for r in rows}


async def load_category_map(conn: asyncpg.Connection) -> dict[str, object]:
    rows = await conn.fetch("SELECT id, code FROM product_categories")
    return {r["code"].upper(): r["id"] for r in rows}


async def backfill_tenant(
    conn: asyncpg.Connection,
    tenant_id,
    tenant_name: str,
) -> None:
    print(f"\n=== tenant {tenant_name} ({tenant_id}) ===")

    brands = await seed_brands(conn, tenant_id)
    cats = await load_category_map(conn)
    pl_set = {_norm(d) for d in M_PRIVATA_DESCS}

    # Agregare distinct product_code: nume + categorie dominantă + flag sika.
    # Folosim `mode() WITHIN GROUP` pentru categorie = cea mai frecventă
    # per cod (rar apar coduri mixte, dar e mai robust).
    rows = await conn.fetch(
        """
        WITH src AS (
            SELECT
                rs.product_code AS code,
                rs.product_name AS name,
                COALESCE(NULLIF(rs.category_code, ''), 'DIVERSE') AS cat,
                ib.source AS source
            FROM raw_sales rs
            JOIN import_batches ib ON ib.id = rs.batch_id
            WHERE rs.tenant_id = $1
              AND rs.product_code IS NOT NULL
              AND rs.product_code <> ''
        )
        SELECT
            code,
            (array_agg(name ORDER BY name))[1] AS name,
            mode() WITHIN GROUP (ORDER BY cat) AS cat,
            BOOL_OR(source LIKE 'sika%') AS is_sika
        FROM src
        GROUP BY code
        """,
        tenant_id,
    )
    print(f"  {len(rows)} coduri produs distincte")

    brand_adeplast = brands["Adeplast"]
    brand_sika = brands["Sika"]
    brand_pl = brands["Marca Privata"]

    def _classify_sika(name: str) -> str:
        """Mapează un produs Sika la o categorie canonică (MU/EPS/UMEDE/DIBLURI)."""
        for pat, code in SIKA_RULES:
            if pat.search(name or ""):
                return code
        return SIKA_FALLBACK_CAT

    inserted = 0
    for r in rows:
        code = r["code"]
        name = r["name"] or code
        cat = (r["cat"] or "DIVERSE").upper()
        is_sika = bool(r["is_sika"])

        if is_sika:
            brand_id = brand_sika
            brand_legacy = "Sika"
            # Override categoria: Sika are coduri proprii (RO01xx) care nu
            # sunt business-relevante — mapăm la MU/EPS/UMEDE/DIBLURI.
            cat = _classify_sika(name)
        elif _norm(name) in pl_set:
            brand_id = brand_pl
            brand_legacy = "Marca Privata"
        else:
            brand_id = brand_adeplast
            brand_legacy = "Adeplast"

        category_id = cats.get(cat)

        status = await conn.execute(
            """
            INSERT INTO products
                (id, tenant_id, code, name, category, brand, category_id, brand_id, active, created_at)
            VALUES
                (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, TRUE, NOW())
            ON CONFLICT ON CONSTRAINT uq_products_tenant_code DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                brand = EXCLUDED.brand,
                category_id = COALESCE(EXCLUDED.category_id, products.category_id),
                brand_id = COALESCE(EXCLUDED.brand_id, products.brand_id)
            """,
            tenant_id, code, name, cat, brand_legacy, category_id, brand_id,
        )
        if status.endswith(" 1"):
            inserted += 1

    print(f"  products: {inserted} insert-uri noi (restul UPDATE)")

    # Seed product_aliases (identity raw_code → product.code).
    status = await conn.execute(
        """
        INSERT INTO product_aliases (id, tenant_id, raw_code, product_id, resolved_at)
        SELECT gen_random_uuid(), p.tenant_id, p.code, p.id, NOW()
        FROM products p
        WHERE p.tenant_id = $1
        ON CONFLICT ON CONSTRAINT uq_product_aliases_tenant_rawcode DO NOTHING
        """,
        tenant_id,
    )
    print(f"  product_aliases: {status}")

    # Back-fill raw_sales.product_id.
    status = await conn.execute(
        """
        UPDATE raw_sales rs
        SET product_id = pa.product_id
        FROM product_aliases pa
        WHERE rs.tenant_id = $1
          AND rs.product_id IS NULL
          AND pa.tenant_id = rs.tenant_id
          AND pa.raw_code = rs.product_code
        """,
        tenant_id,
    )
    print(f"  raw_sales back-fill: {status}")


async def main() -> None:
    conn = await asyncpg.connect(_pg_dsn())
    try:
        await seed_global_categories(conn)

        tenants = await conn.fetch(
            """
            SELECT DISTINCT t.id, t.name
            FROM tenants t
            JOIN raw_sales rs ON rs.tenant_id = t.id
            ORDER BY t.name
            """
        )
        if not tenants:
            print("niciun tenant cu raw_sales — nimic de făcut")
            return
        for t in tenants:
            await backfill_tenant(conn, t["id"], t["name"])

        print("\n[OK] backfill terminat")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
