"""add gallery photo approval

Revision ID: f1a2b3c4d5e6
Revises: 1be529be512b
Create Date: 2026-04-21 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = '1be529be512b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'gallery_photos',
        sa.Column(
            'approval_status', sa.String(length=20),
            nullable=False, server_default=sa.text("'approved'"),
        ),
    )
    op.add_column(
        'gallery_photos',
        sa.Column('approved_by_user_id', sa.UUID(), nullable=True),
    )
    op.add_column(
        'gallery_photos',
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_gallery_photos_approved_by_user_id',
        'gallery_photos', 'users',
        ['approved_by_user_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_gallery_photos_tenant_status',
        'gallery_photos', ['tenant_id', 'approval_status'],
    )


def downgrade() -> None:
    op.drop_index('ix_gallery_photos_tenant_status', table_name='gallery_photos')
    op.drop_constraint('fk_gallery_photos_approved_by_user_id', 'gallery_photos', type_='foreignkey')
    op.drop_column('gallery_photos', 'approved_at')
    op.drop_column('gallery_photos', 'approved_by_user_id')
    op.drop_column('gallery_photos', 'approval_status')
