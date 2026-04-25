"""add_promotions

Tabele promotii — header `promotions` + copilul `promotion_targets`.
Folosit pentru simulari de impact al promotiilor pe marja.

Revision ID: c2d3e4f5a6b8
Revises: a1b2c3d4e5f7
Create Date: 2026-04-25 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c2d3e4f5a6b8'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS promotions (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            scope VARCHAR(10) NOT NULL,
            name VARCHAR(200) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            discount_type VARCHAR(20) NOT NULL,
            value NUMERIC(14, 4) NOT NULL,
            valid_from DATE NOT NULL,
            valid_to DATE NOT NULL,
            client_filter JSONB,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promotions_tenant_id "
        "ON promotions (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promotions_scope "
        "ON promotions (scope)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promotions_status "
        "ON promotions (status)"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS promotion_targets (
            id UUID PRIMARY KEY,
            promotion_id UUID NOT NULL REFERENCES promotions(id) ON DELETE CASCADE,
            kind VARCHAR(20) NOT NULL,
            key VARCHAR(200) NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promotion_targets_promotion_id "
        "ON promotion_targets (promotion_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS promotion_targets")
    op.execute("DROP TABLE IF EXISTS promotions")
