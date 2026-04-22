"""add store_agent_mappings

Revision ID: a1b2c3d4e5f6
Revises: ec0ec9055e85
Create Date: 2026-04-20 12:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ec0ec9055e85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'store_agent_mappings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('client_original', sa.String(length=255), nullable=False),
        sa.Column('ship_to_original', sa.String(length=255), nullable=False),
        sa.Column('agent_original', sa.String(length=255), nullable=True),
        sa.Column('cod_numeric', sa.String(length=100), nullable=True),
        sa.Column('cheie_finala', sa.String(length=255), nullable=False),
        sa.Column('agent_unificat', sa.String(length=255), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=True),
        sa.Column('agent_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'source', 'client_original', 'ship_to_original',
            name='uq_store_agent_mappings_tenant_src_client_ship',
        ),
    )
    op.create_index('ix_store_agent_mappings_tenant_id',
                    'store_agent_mappings', ['tenant_id'])
    op.create_index('ix_store_agent_mappings_source',
                    'store_agent_mappings', ['source'])
    op.create_index('ix_store_agent_mappings_client_original',
                    'store_agent_mappings', ['client_original'])
    op.create_index('ix_store_agent_mappings_ship_to_original',
                    'store_agent_mappings', ['ship_to_original'])
    op.create_index('ix_store_agent_mappings_cheie_finala',
                    'store_agent_mappings', ['cheie_finala'])
    op.create_index('ix_store_agent_mappings_agent_unificat',
                    'store_agent_mappings', ['agent_unificat'])
    op.create_index('ix_store_agent_mappings_store_id',
                    'store_agent_mappings', ['store_id'])
    op.create_index('ix_store_agent_mappings_agent_id',
                    'store_agent_mappings', ['agent_id'])


def downgrade() -> None:
    op.drop_table('store_agent_mappings')
