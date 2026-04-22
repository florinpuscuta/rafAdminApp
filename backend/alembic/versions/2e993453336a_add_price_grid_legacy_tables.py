"""add_price_grid_legacy_tables

Revision ID: 2e993453336a
Revises: e4a71c8f92b3
Create Date: 2026-04-20 18:08:13.817988
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '2e993453336a'
down_revision: Union[str, None] = 'e4a71c8f92b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_grid',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('company', sa.String(length=20), nullable=False),
        sa.Column('store', sa.String(length=80), nullable=False),
        sa.Column('row_idx', sa.Integer(), nullable=False),
        sa.Column('row_num', sa.String(length=50), nullable=True),
        sa.Column('group_label', sa.String(length=200), nullable=True),
        sa.Column('brand_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('import_source', sa.String(length=50), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('legacy_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'company', 'store', 'row_idx',
            name='uq_price_grid_tenant_company_store_row',
        ),
    )
    op.create_index(op.f('ix_price_grid_company'), 'price_grid', ['company'], unique=False)
    op.create_index(op.f('ix_price_grid_legacy_id'), 'price_grid', ['legacy_id'], unique=False)
    op.create_index(op.f('ix_price_grid_store'), 'price_grid', ['store'], unique=False)
    op.create_index(op.f('ix_price_grid_tenant_id'), 'price_grid', ['tenant_id'], unique=False)

    op.create_table(
        'price_grid_meta',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('company', sa.String(length=20), nullable=False),
        sa.Column('store', sa.String(length=80), nullable=False),
        sa.Column('date_prices', sa.String(length=30), nullable=True),
        sa.Column('brands', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('imported_by', sa.String(length=200), nullable=True),
        sa.Column('imported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'company', 'store', name='pk_price_grid_meta'),
    )


def downgrade() -> None:
    op.drop_table('price_grid_meta')
    op.drop_index(op.f('ix_price_grid_tenant_id'), table_name='price_grid')
    op.drop_index(op.f('ix_price_grid_store'), table_name='price_grid')
    op.drop_index(op.f('ix_price_grid_legacy_id'), table_name='price_grid')
    op.drop_index(op.f('ix_price_grid_company'), table_name='price_grid')
    op.drop_table('price_grid')
