"""add_targhet_growth_pct

Tabel nou `targhet_growth_pct` — procentul de creștere față de an precedent
salvat per (tenant, year, month). Folosit de pagina Targhet (editabil pe
SIKADP) pentru a permite diferentieri sezoniere. Scope-less: o singură
valoare per lună, aplicată la toate scope-urile (adp/sika/sikadp) și la
calculul Zona Agent din Evaluare.

Revision ID: f2b3c4d5e6a7
Revises: e9a2b4c6d8f1
Create Date: 2026-04-23 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f2b3c4d5e6a7'
down_revision: Union[str, None] = 'e9a2b4c6d8f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS targhet_growth_pct (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            pct        NUMERIC(6,2) NOT NULL DEFAULT 10,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_targhet_growth_pct_tenant_ym
        ON targhet_growth_pct (tenant_id, year, month);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS targhet_growth_pct;")
