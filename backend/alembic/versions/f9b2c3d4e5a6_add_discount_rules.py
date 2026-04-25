"""add_discount_rules

Tabel pentru reguli de discount retroactiv per (client KA, scope, grupa).
Default = applies TRUE; salvam explicit doar exclusii.

Revision ID: f9b2c3d4e5a6
Revises: e8a3b4c5d6f7
Create Date: 2026-04-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f9b2c3d4e5a6'
down_revision: Union[str, None] = 'e8a3b4c5d6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS discount_rules (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            client_canonical VARCHAR(255) NOT NULL,
            scope VARCHAR(10) NOT NULL,
            group_kind VARCHAR(20) NOT NULL,
            group_key VARCHAR(100) NOT NULL,
            applies BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_discount_rules_tenant_client_scope_group
                UNIQUE (tenant_id, client_canonical, scope, group_kind, group_key)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_discount_rules_tenant_id "
        "ON discount_rules (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_discount_rules_client_canonical "
        "ON discount_rules (client_canonical)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_discount_rules_scope "
        "ON discount_rules (scope)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS discount_rules")
