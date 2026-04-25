"""add_production_prices_monthly

Snapshot lunar al pretului de productie. Folosit de "Analiza Marja Lunara".
Cand lipseste pentru o luna, dashboard-ul foloseste fallback pe
`production_prices` (medie) cu disclaimer.

Revision ID: a1b2c3d4e5f7
Revises: f9b2c3d4e5a6
Create Date: 2026-04-25 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'f9b2c3d4e5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS production_prices_monthly (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            scope VARCHAR(10) NOT NULL,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            price NUMERIC(14, 4) NOT NULL,
            last_imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_imported_filename VARCHAR(500),
            CONSTRAINT uq_production_prices_monthly_tenant_scope_product_period
                UNIQUE (tenant_id, scope, product_id, year, month)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_monthly_tenant_id "
        "ON production_prices_monthly (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_monthly_scope "
        "ON production_prices_monthly (scope)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_monthly_product_id "
        "ON production_prices_monthly (product_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_monthly_year_month "
        "ON production_prices_monthly (year, month)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_prices_monthly")
