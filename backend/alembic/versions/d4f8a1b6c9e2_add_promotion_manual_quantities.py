"""add_promotion_manual_quantities

Adauga coloana JSONB `manual_quantities` pe `promotions` pentru a salva
estimarile manuale de cantitate per produs (folosite la simulare si la
calibrare post-promotie).

Revision ID: d4f8a1b6c9e2
Revises: b1c2d3e4f5a7
Create Date: 2026-04-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4f8a1b6c9e2'
down_revision: Union[str, None] = 'b1c2d3e4f5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE promotions "
        "ADD COLUMN IF NOT EXISTS manual_quantities JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE promotions DROP COLUMN IF EXISTS manual_quantities")
