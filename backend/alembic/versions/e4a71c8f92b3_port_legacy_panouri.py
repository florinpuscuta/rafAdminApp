"""port_legacy_panouri

Port 1:1 al schemei legacy `adeplast-dashboard/routes/gallery.py` (tabel
`panouri_standuri`).

Înlocuiește tabela simplistă `panou_items` (creată în `722a52111e84_add_
marketing_tables.py`) cu schema originală din legacy, ajustată pentru SaaS:
  - UUID PK (în loc de INTEGER AUTOINCREMENT)
  - tenant_id pe fiecare rând (CASCADE pe tenants)
  - store_name TEXT (legacy folosea `cheie_finala` din unified_store_agent_map)
  - panel_type TEXT (default 'panou'), title, width_cm REAL, height_cm REAL,
    location_in_store, notes, photo_filename, photo_thumb, agent, created_by
  - legacy_id INTEGER (pentru import din users.db)

DROP-ul lui `panou_items` e sigur — a fost introdus ieri (2026-04-20) și nu
conține date de producție.

Revision ID: e4a71c8f92b3
Revises: d8f1a4c9e201
Create Date: 2026-04-20 23:00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e4a71c8f92b3"
down_revision: Union[str, None] = "d8f1a4c9e201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Drop vechea tabelă `panou_items` (schema simplistă din 722a52111e84).
    op.execute("DROP TABLE IF EXISTS panou_items CASCADE;")

    # 2) Recreează tabela oglindind schema legacy `panouri_standuri`.
    op.execute(
        """
        CREATE TABLE panouri_standuri (
            id                  UUID PRIMARY KEY,
            tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            store_name          VARCHAR(255) NOT NULL,
            panel_type          VARCHAR(50) NOT NULL DEFAULT 'panou',
            title               VARCHAR(300) NULL,
            width_cm            DOUBLE PRECISION NULL,
            height_cm           DOUBLE PRECISION NULL,
            location_in_store   VARCHAR(300) NULL,
            notes               TEXT NULL,
            photo_filename      VARCHAR(500) NULL,
            photo_thumb         VARCHAR(500) NULL,
            agent               VARCHAR(255) NULL,
            created_by          VARCHAR(255) NULL,
            legacy_id           INTEGER NULL,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_panouri_standuri_tenant_id  ON panouri_standuri (tenant_id);")
    op.execute("CREATE INDEX ix_panouri_standuri_store_name ON panouri_standuri (store_name);")
    op.execute("CREATE INDEX ix_panouri_standuri_panel_type ON panouri_standuri (panel_type);")
    op.execute("CREATE INDEX ix_panouri_standuri_agent      ON panouri_standuri (agent);")
    op.execute("CREATE INDEX ix_panouri_standuri_legacy_id  ON panouri_standuri (legacy_id);")


def downgrade() -> None:
    # Inversul: drop tabela portată și recreează `panou_items` simplist.
    op.execute("DROP TABLE IF EXISTS panouri_standuri CASCADE;")
    op.execute(
        """
        CREATE TABLE panou_items (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            store_id UUID NULL REFERENCES stores(id) ON DELETE SET NULL,
            kind VARCHAR(20) NOT NULL,
            location VARCHAR(300) NULL,
            installed_at TIMESTAMPTZ NULL,
            removed_at TIMESTAMPTZ NULL,
            notes TEXT NULL,
            photo_url VARCHAR(500) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX ix_panou_items_tenant_id ON panou_items (tenant_id);")
    op.execute("CREATE INDEX ix_panou_items_store_id ON panou_items (store_id);")
    op.execute("CREATE INDEX ix_panou_items_kind ON panou_items (kind);")
