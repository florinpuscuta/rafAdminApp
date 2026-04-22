"""add_app_settings

Revision ID: 1be529be512b
Revises: a444b94f471d
Create Date: 2026-04-20 18:36:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1be529be512b'
down_revision: Union[str, None] = 'a444b94f471d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'key', name='pk_app_settings'),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
