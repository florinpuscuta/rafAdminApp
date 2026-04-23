"""add_agent_store_bonus

Tabel nou `agent_store_bonus` pentru "Zona Agent": pentru fiecare
(agent, magazin, lună) se înregistrează manual un bonus. Suma pe
toate magazinele agentului se agregă în "Bonus zonă" din matricea
lunară a agentului (înlocuiește rolul `store_contact_bonus`).

Revision ID: e9a2b4c6d8f1
Revises: d5e8f9a1b2c3
Create Date: 2026-04-23 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e9a2b4c6d8f1'
down_revision: Union[str, None] = 'd5e8f9a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_store_bonus (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            agent_id   UUID NOT NULL REFERENCES agents(id)  ON DELETE CASCADE,
            store_id   UUID NOT NULL REFERENCES stores(id)  ON DELETE CASCADE,
            year       INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            bonus      NUMERIC(12,2) NOT NULL DEFAULT 0,
            note       VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_store_bonus_tenant_agent_store_ym
        ON agent_store_bonus (tenant_id, agent_id, store_id, year, month);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_store_bonus_tenant_agent_ym
        ON agent_store_bonus (tenant_id, agent_id, year, month);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_store_bonus;")
