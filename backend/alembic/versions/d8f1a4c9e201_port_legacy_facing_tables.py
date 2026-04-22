"""port_legacy_facing_tables

Port 1:1 al schemei legacy `adeplast-dashboard/services/facing_service.py`.

Înlocuiește schema simplistă (year/month/store_id FK la stores) introdusă în
`722a52111e84_add_marketing_tables.py` cu schema originală:
  - facing_raioane      (tree via parent_id, sort_order, legacy_id)
  - facing_brands       (is_own, color, sort_order, legacy_id)
  - facing_snapshots    (store_name TEXT, luna "YYYY-MM", nr_fete)
  - facing_history      (audit log — raion_id/brand_id nullable pt. store-delete)
  - facing_chain_brands (matrice retea x brand, cheie compusă)

DROP-urile sunt sigure: tabelele au fost introduse ieri (2026-04-20) și nu
conțin date de producție — doar seed-ul generat de agentul anterior.

Revision ID: d8f1a4c9e201
Revises: 722a52111e84
Create Date: 2026-04-20 22:00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d8f1a4c9e201"
down_revision: Union[str, None] = "722a52111e84"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Drop vechile tabele facing_* (schema simplistă din 722a52111e84).
    #    `panou_items` NU se atinge — ține de alt feature (mkt_panouri).
    op.execute("DROP TABLE IF EXISTS facing_snapshots CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_raioane CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_brands CASCADE;")

    # 2) Recreează tabelele oglindind schema legacy (SQLite users.db).
    op.execute(
        """
        CREATE TABLE facing_raioane (
            id          UUID PRIMARY KEY,
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name        VARCHAR(150) NOT NULL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            parent_id   UUID NULL REFERENCES facing_raioane(id) ON DELETE CASCADE,
            legacy_id   INTEGER NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_facing_raioane_tenant_name UNIQUE (tenant_id, name)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_raioane_tenant_id ON facing_raioane (tenant_id);")
    op.execute("CREATE INDEX ix_facing_raioane_parent_id ON facing_raioane (parent_id);")
    op.execute("CREATE INDEX ix_facing_raioane_legacy_id ON facing_raioane (legacy_id);")

    op.execute(
        """
        CREATE TABLE facing_brands (
            id          UUID PRIMARY KEY,
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name        VARCHAR(150) NOT NULL,
            color       VARCHAR(20) NOT NULL DEFAULT '#888888',
            is_own      BOOLEAN NOT NULL DEFAULT FALSE,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            active      BOOLEAN NOT NULL DEFAULT TRUE,
            legacy_id   INTEGER NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_facing_brands_tenant_name UNIQUE (tenant_id, name)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_brands_tenant_id ON facing_brands (tenant_id);")
    op.execute("CREATE INDEX ix_facing_brands_legacy_id ON facing_brands (legacy_id);")

    op.execute(
        """
        CREATE TABLE facing_snapshots (
            id          UUID PRIMARY KEY,
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            store_name  VARCHAR(255) NOT NULL,
            raion_id    UUID NOT NULL REFERENCES facing_raioane(id) ON DELETE CASCADE,
            brand_id    UUID NOT NULL REFERENCES facing_brands(id) ON DELETE CASCADE,
            luna        VARCHAR(7) NOT NULL,
            nr_fete     INTEGER NOT NULL DEFAULT 0,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_by  VARCHAR(255) NULL,
            CONSTRAINT uq_facing_snap_tenant_store_raion_brand_luna
                UNIQUE (tenant_id, store_name, raion_id, brand_id, luna)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_snapshots_tenant_id ON facing_snapshots (tenant_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_store_name ON facing_snapshots (store_name);")
    op.execute("CREATE INDEX ix_facing_snapshots_raion_id ON facing_snapshots (raion_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_brand_id ON facing_snapshots (brand_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_luna ON facing_snapshots (luna);")

    op.execute(
        """
        CREATE TABLE facing_history (
            id               UUID PRIMARY KEY,
            tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            store_name       VARCHAR(255) NOT NULL,
            raion_id         UUID NULL,
            brand_id         UUID NULL,
            luna             VARCHAR(7) NOT NULL,
            nr_fete          INTEGER NOT NULL DEFAULT 0,
            action           VARCHAR(64) NOT NULL DEFAULT 'update',
            changed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            changed_by       VARCHAR(255) NULL,
            legacy_raion_id  INTEGER NULL,
            legacy_brand_id  INTEGER NULL
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_history_tenant_id ON facing_history (tenant_id);")
    op.execute("CREATE INDEX ix_facing_history_store_name ON facing_history (store_name);")
    op.execute("CREATE INDEX ix_facing_history_raion_id ON facing_history (raion_id);")
    op.execute("CREATE INDEX ix_facing_history_brand_id ON facing_history (brand_id);")

    op.execute(
        """
        CREATE TABLE facing_chain_brands (
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            chain       VARCHAR(100) NOT NULL,
            brand_id    UUID NOT NULL REFERENCES facing_brands(id) ON DELETE CASCADE,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            CONSTRAINT pk_facing_chain_brands PRIMARY KEY (tenant_id, chain, brand_id)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_chain_brands_chain ON facing_chain_brands (chain);")


def downgrade() -> None:
    # Inversul: drop tabelele portate si recreeaza schema "simplista" introdusa
    # in 722a52111e84 (pentru completitudine — practic nu vom downgrade).
    op.execute("DROP TABLE IF EXISTS facing_chain_brands CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_history CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_snapshots CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_brands CASCADE;")
    op.execute("DROP TABLE IF EXISTS facing_raioane CASCADE;")

    # Recreare schema din 722a52111e84 (simplistă).
    op.execute(
        """
        CREATE TABLE facing_brands (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(150) NOT NULL,
            color VARCHAR(20) NULL,
            is_own BOOLEAN NOT NULL,
            display_order INTEGER NOT NULL,
            active BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_facing_brands_tenant_name UNIQUE (tenant_id, name)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_brands_tenant_id ON facing_brands (tenant_id);")
    op.execute(
        """
        CREATE TABLE facing_raioane (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(150) NOT NULL,
            parent_id UUID NULL REFERENCES facing_raioane(id) ON DELETE CASCADE,
            display_order INTEGER NOT NULL,
            active BOOLEAN NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_facing_raioane_tenant_name UNIQUE (tenant_id, name)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_raioane_tenant_id ON facing_raioane (tenant_id);")
    op.execute("CREATE INDEX ix_facing_raioane_parent_id ON facing_raioane (parent_id);")
    op.execute(
        """
        CREATE TABLE facing_snapshots (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            raion_id UUID NOT NULL REFERENCES facing_raioane(id) ON DELETE CASCADE,
            brand_id UUID NOT NULL REFERENCES facing_brands(id) ON DELETE CASCADE,
            facings_count INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_facing_snap_tenant_ym_store_raion_brand
                UNIQUE (tenant_id, year, month, store_id, raion_id, brand_id)
        );
        """
    )
    op.execute("CREATE INDEX ix_facing_snapshots_tenant_id ON facing_snapshots (tenant_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_year ON facing_snapshots (year);")
    op.execute("CREATE INDEX ix_facing_snapshots_month ON facing_snapshots (month);")
    op.execute("CREATE INDEX ix_facing_snapshots_store_id ON facing_snapshots (store_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_raion_id ON facing_snapshots (raion_id);")
    op.execute("CREATE INDEX ix_facing_snapshots_brand_id ON facing_snapshots (brand_id);")
