"""enable pg_trgm

Revision ID: b1c2d3e4f5a7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-25

Folosit la cross-KA pricing pentru match nearest-neighbor pe nume produs
(prices.service._resolve_label_categories).
"""
from alembic import op


revision = "b1c2d3e4f5a7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
