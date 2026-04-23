"""add_bonus_vanzari_eligibil

Adauga flag persistent `bonus_vanzari_eligibil` pe `agent_compensation`
pentru a marca agentii care nu primesc bonus de vanzari (e.g., Sava, Panove).
Default true — toti agentii existenti raman eligibili.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-04-23 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE agent_compensation
            ADD COLUMN IF NOT EXISTS bonus_vanzari_eligibil BOOLEAN NOT NULL DEFAULT true;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE agent_compensation
            DROP COLUMN IF EXISTS bonus_vanzari_eligibil;
    """)
