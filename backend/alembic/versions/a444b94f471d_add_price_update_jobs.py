"""add_price_update_jobs

Revision ID: a444b94f471d
Revises: 2e993453336a
Create Date: 2026-04-20 18:22:44.317567
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a444b94f471d'
down_revision: Union[str, None] = '2e993453336a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'price_update_jobs',
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('company', sa.String(length=20), nullable=False),
        sa.Column('store', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('processed', sa.Integer(), nullable=False),
        sa.Column('found', sa.Integer(), nullable=False),
        sa.Column('not_found', sa.Integer(), nullable=False),
        sa.Column('errors', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_msg', sa.String(length=500), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('job_id'),
    )
    op.create_index(op.f('ix_price_update_jobs_store'), 'price_update_jobs', ['store'], unique=False)
    op.create_index(op.f('ix_price_update_jobs_tenant_id'), 'price_update_jobs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_price_update_jobs_tenant_id'), table_name='price_update_jobs')
    op.drop_index(op.f('ix_price_update_jobs_store'), table_name='price_update_jobs')
    op.drop_table('price_update_jobs')
