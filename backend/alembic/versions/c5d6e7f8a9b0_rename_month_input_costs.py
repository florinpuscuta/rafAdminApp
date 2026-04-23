"""rename_month_input_costs

Redenumeste coloanele de costuri din `agent_month_inputs` pentru a reflecta
semantica noua:
  cost_combustibil_ron -> merchandiser_zona_ron
  cost_revizii_ron     -> cheltuieli_auto_ron
  alte_costuri_ron     -> alte_cheltuieli_ron
Adauga `alte_cheltuieli_label` (text, nullable) — eticheta libera pentru
cheltuiala diversa.

Revision ID: c5d6e7f8a9b0
Revises: f2b3c4d5e6a7
Create Date: 2026-04-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'f2b3c4d5e6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN cost_combustibil_ron TO merchandiser_zona_ron;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN cost_revizii_ron TO cheltuieli_auto_ron;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN alte_costuri_ron TO alte_cheltuieli_ron;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            ADD COLUMN IF NOT EXISTS alte_cheltuieli_label VARCHAR(100);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE agent_month_inputs
            DROP COLUMN IF EXISTS alte_cheltuieli_label;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN alte_cheltuieli_ron TO alte_costuri_ron;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN cheltuieli_auto_ron TO cost_revizii_ron;
    """)
    op.execute("""
        ALTER TABLE agent_month_inputs
            RENAME COLUMN merchandiser_zona_ron TO cost_combustibil_ron;
    """)
