"""add facing_raion_competitors matrix

Matrice configurabilă (own_brand × competitor × sub_raion) pentru
Dash Face Tracker. Înlocuiește configul hardcodat din cod cu tabel DB.

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e6
Create Date: 2026-04-22 00:00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE facing_raion_competitors (
            tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            raion_id            UUID NOT NULL REFERENCES facing_raioane(id) ON DELETE CASCADE,
            own_brand_id        UUID NOT NULL REFERENCES facing_brands(id) ON DELETE CASCADE,
            competitor_brand_id UUID NOT NULL REFERENCES facing_brands(id) ON DELETE CASCADE,
            sort_order          INTEGER NOT NULL DEFAULT 0,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT pk_facing_raion_competitors
              PRIMARY KEY (tenant_id, raion_id, own_brand_id, competitor_brand_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_facing_raion_comp_tenant_own "
        "ON facing_raion_competitors (tenant_id, own_brand_id);"
    )
    op.execute(
        "CREATE INDEX ix_facing_raion_comp_tenant_raion "
        "ON facing_raion_competitors (tenant_id, raion_id);"
    )

    # Seed inițial: transpune configul hardcodat în DB pentru toate tenant-urile
    # existente. Regulile:
    #   Adeplast la toate sub-raioanele din Constructii + Gresie/faianță:
    #     concurenți = Ceresit, 4 Maini, Baumit
    #     + la Chituri: + Sika
    #     + la Paleti:  + Mapei, Sika
    #   Sika la toate sub-raioanele din Constructii + Gresie/faianță + Chimice:
    #     concurenți = Mapei, Soudal, Bostik
    #     + la Chituri: + Adeplast
    #     + la Paleti:  + Adeplast
    op.execute(
        """
        WITH
        own_adeplast AS (
          SELECT tenant_id, id AS brand_id FROM facing_brands WHERE name = 'Adeplast'
        ),
        own_sika AS (
          SELECT tenant_id, id AS brand_id FROM facing_brands WHERE name = 'Sika'
        ),
        sub_constructii AS (
          SELECT c.tenant_id, c.id AS raion_id, c.name
          FROM facing_raioane c
          JOIN facing_raioane p ON p.id = c.parent_id
          WHERE p.name = 'Constructii'
        ),
        sub_gresie AS (
          SELECT c.tenant_id, c.id AS raion_id, c.name
          FROM facing_raioane c
          JOIN facing_raioane p ON p.id = c.parent_id
          WHERE p.name = 'Gresie și faianță'
        ),
        sub_chimice AS (
          SELECT c.tenant_id, c.id AS raion_id, c.name
          FROM facing_raioane c
          JOIN facing_raioane p ON p.id = c.parent_id
          WHERE p.name = 'Chimice'
        ),
        adeplast_subs AS (
          SELECT tenant_id, raion_id, name FROM sub_constructii
          UNION ALL
          SELECT tenant_id, raion_id, name FROM sub_gresie
        ),
        sika_subs AS (
          SELECT tenant_id, raion_id, name FROM sub_constructii
          UNION ALL
          SELECT tenant_id, raion_id, name FROM sub_gresie
          UNION ALL
          SELECT tenant_id, raion_id, name FROM sub_chimice
        )
        -- Adeplast vs concurenți standard
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT s.tenant_id, s.raion_id, o.brand_id, b.id, 0
        FROM adeplast_subs s
        JOIN own_adeplast o ON o.tenant_id = s.tenant_id
        JOIN facing_brands b ON b.tenant_id = s.tenant_id
          AND b.name IN ('Ceresit', '4 Maini', 'Baumit')
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        -- Adeplast la Chituri: + Sika
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT c.tenant_id, c.id, o.id, b.id, 10
        FROM facing_raioane c
        JOIN facing_raioane p ON p.id = c.parent_id AND p.name = 'Gresie și faianță'
        JOIN facing_brands o ON o.tenant_id = c.tenant_id AND o.name = 'Adeplast'
        JOIN facing_brands b ON b.tenant_id = c.tenant_id AND b.name = 'Sika'
        WHERE c.name = 'Chituri'
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        -- Adeplast la Paleti: + Mapei, Sika
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT c.tenant_id, c.id, o.id, b.id, 10
        FROM facing_raioane c
        JOIN facing_raioane p ON p.id = c.parent_id AND p.name = 'Constructii'
        JOIN facing_brands o ON o.tenant_id = c.tenant_id AND o.name = 'Adeplast'
        JOIN facing_brands b ON b.tenant_id = c.tenant_id AND b.name IN ('Mapei', 'Sika')
        WHERE c.name = 'Paleti'
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        -- Sika vs concurenți standard
        WITH sub_all AS (
          SELECT c.tenant_id, c.id AS raion_id, c.name
          FROM facing_raioane c
          JOIN facing_raioane p ON p.id = c.parent_id
          WHERE p.name IN ('Constructii', 'Gresie și faianță', 'Chimice')
        )
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT s.tenant_id, s.raion_id, o.id, b.id, 0
        FROM sub_all s
        JOIN facing_brands o ON o.tenant_id = s.tenant_id AND o.name = 'Sika'
        JOIN facing_brands b ON b.tenant_id = s.tenant_id
          AND b.name IN ('Mapei', 'Soudal', 'Bostik')
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        -- Sika la Chituri: + Adeplast
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT c.tenant_id, c.id, o.id, b.id, 10
        FROM facing_raioane c
        JOIN facing_raioane p ON p.id = c.parent_id AND p.name = 'Gresie și faianță'
        JOIN facing_brands o ON o.tenant_id = c.tenant_id AND o.name = 'Sika'
        JOIN facing_brands b ON b.tenant_id = c.tenant_id AND b.name = 'Adeplast'
        WHERE c.name = 'Chituri'
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        -- Sika la Paleti: + Adeplast
        INSERT INTO facing_raion_competitors
          (tenant_id, raion_id, own_brand_id, competitor_brand_id, sort_order)
        SELECT c.tenant_id, c.id, o.id, b.id, 10
        FROM facing_raioane c
        JOIN facing_raioane p ON p.id = c.parent_id AND p.name = 'Constructii'
        JOIN facing_brands o ON o.tenant_id = c.tenant_id AND o.name = 'Sika'
        JOIN facing_brands b ON b.tenant_id = c.tenant_id AND b.name = 'Adeplast'
        WHERE c.name = 'Paleti'
        ON CONFLICT DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS facing_raion_competitors CASCADE;")
