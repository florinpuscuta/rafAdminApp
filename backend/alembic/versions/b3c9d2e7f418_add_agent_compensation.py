"""add_agent_compensation

Creează tabelul `agent_compensation` pentru feature-ul Evaluare Agenți.
Un agent = max. 1 rând (unique pe tenant_id + agent_id).

Revision ID: b3c9d2e7f418
Revises: a9b8c7d6e5f4
Create Date: 2026-04-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b3c9d2e7f418'
down_revision: Union[str, None] = 'a9b8c7d6e5f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_compensation (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            salariu_fix NUMERIC(12,2) NOT NULL DEFAULT 0,
            telefon_flat NUMERIC(12,2) NOT NULL DEFAULT 0,
            diurna_flat NUMERIC(12,2) NOT NULL DEFAULT 0,
            consum_l_100km NUMERIC(6,2) NOT NULL DEFAULT 0,
            pret_carburant_ron_l NUMERIC(8,3) NOT NULL DEFAULT 0,
            note VARCHAR(500) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_agent_comp_tenant_agent UNIQUE (tenant_id, agent_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_compensation_tenant_id ON agent_compensation (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_compensation_agent_id ON agent_compensation (agent_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_compensation;")
