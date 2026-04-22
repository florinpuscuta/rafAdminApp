"""add raw_sales.client_code

Revision ID: b2e5a94cfd01
Revises: a1b2c3d4e5f6
Create Date: 2026-04-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2e5a94cfd01"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raw_sales",
        sa.Column("client_code", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_raw_sales_client_code", "raw_sales", ["client_code"],
    )


def downgrade() -> None:
    op.drop_index("ix_raw_sales_client_code", table_name="raw_sales")
    op.drop_column("raw_sales", "client_code")
