"""add_month_inputs_and_raion_bonus

Creează tabelele `agent_month_inputs` și `store_contact_bonus` pentru
feature-ul Evaluare Agenți (input lunar km + carburant; bonusări lunare
pentru oamenii de raion din magazine).

Revision ID: c4d7e8f9a210
Revises: b3c9d2e7f418
Create Date: 2026-04-23 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4d7e8f9a210'
down_revision: Union[str, None] = 'b3c9d2e7f418'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agent_month_inputs (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            year INT NOT NULL,
            month INT NOT NULL,
            km NUMERIC(10,2) NOT NULL DEFAULT 0,
            pret_carburant_ron_l_snapshot NUMERIC(8,3) NULL,
            note VARCHAR(500) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_agent_month_inputs_tenant_agent_ym UNIQUE (tenant_id, agent_id, year, month)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_month_inputs_tenant_id ON agent_month_inputs (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_month_inputs_agent_id ON agent_month_inputs (agent_id);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS store_contact_bonus (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
            agent_id UUID NULL REFERENCES agents(id) ON DELETE SET NULL,
            year INT NOT NULL,
            month INT NOT NULL,
            contact_name VARCHAR(255) NOT NULL,
            suma NUMERIC(12,2) NOT NULL DEFAULT 0,
            note VARCHAR(500) NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_contact_bonus_tenant_id ON store_contact_bonus (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_contact_bonus_store_id ON store_contact_bonus (store_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_contact_bonus_agent_id ON store_contact_bonus (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_contact_bonus_year_month ON store_contact_bonus (tenant_id, year, month);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS store_contact_bonus;")
    op.execute("DROP TABLE IF EXISTS agent_month_inputs;")
