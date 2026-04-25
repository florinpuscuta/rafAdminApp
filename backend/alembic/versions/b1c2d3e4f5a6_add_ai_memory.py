"""add ai_memory: persistent key-value memory for AI assistant

Revision ID: b1c2d3e4f5a6
Revises: d6e7f8a9b0c1
Create Date: 2026-04-25 06:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_memory',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'user_id', 'key', name='uq_ai_memory_tenant_user_key'
        ),
    )
    op.create_index(
        op.f('ix_ai_memory_tenant_id'), 'ai_memory', ['tenant_id'], unique=False,
    )
    op.create_index(
        op.f('ix_ai_memory_user_id'), 'ai_memory', ['user_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_memory_user_id'), table_name='ai_memory')
    op.drop_index(op.f('ix_ai_memory_tenant_id'), table_name='ai_memory')
    op.drop_table('ai_memory')
