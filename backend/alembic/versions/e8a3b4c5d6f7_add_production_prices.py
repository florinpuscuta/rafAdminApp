"""add_production_prices

Tabel pentru preturile de productie incarcate via Excel — sursa pentru
calculul de marja. Un singur pret activ pe (tenant, scope[adp|sika], product).

Revision ID: e8a3b4c5d6f7
Revises: d6e7f8a9b0c1
Create Date: 2026-04-25 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e8a3b4c5d6f7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS production_prices (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            scope VARCHAR(10) NOT NULL,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            price NUMERIC(14, 4) NOT NULL,
            last_imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_imported_filename VARCHAR(500),
            CONSTRAINT uq_production_prices_tenant_scope_product
                UNIQUE (tenant_id, scope, product_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_tenant_id "
        "ON production_prices (tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_scope "
        "ON production_prices (scope)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_production_prices_product_id "
        "ON production_prices (product_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS production_prices;")
