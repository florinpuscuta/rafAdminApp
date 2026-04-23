"""add_month_input_direct_costs

Adaugă coloanele de costuri lunare directe pe `agent_month_inputs`:
`cost_combustibil_ron`, `cost_revizii_ron`, `alte_costuri_ron`. Toate se
introduc manual (în RON) — nu mai folosim km × consum × preț.

Revision ID: d5e8f9a1b2c3
Revises: c4d7e8f9a210
Create Date: 2026-04-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd5e8f9a1b2c3'
down_revision: Union[str, None] = 'c4d7e8f9a210'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE agent_month_inputs
        ADD COLUMN IF NOT EXISTS cost_combustibil_ron NUMERIC(12,2) NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS cost_revizii_ron     NUMERIC(12,2) NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS alte_costuri_ron     NUMERIC(12,2) NOT NULL DEFAULT 0;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE agent_month_inputs
        DROP COLUMN IF EXISTS alte_costuri_ron,
        DROP COLUMN IF EXISTS cost_revizii_ron,
        DROP COLUMN IF EXISTS cost_combustibil_ron;
    """)
