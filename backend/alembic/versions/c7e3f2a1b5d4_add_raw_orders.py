"""add raw_orders (ADP + Sika)

Revision ID: c7e3f2a1b5d4
Revises: b2e5a94cfd01
Create Date: 2026-04-20 15:00:00.000000

Un singur tabel raw_orders captează comenzile open de la ambele surse:
- ADP (radComenzi): per-sheet KA (Dedeman/Altex/…), status NELIVRAT/NEFACTURAT,
  cu nr_comanda, ind, data_livrare, cant_rest
- Sika (comenzi): un sheet, status implicit OPEN, doar qty+amount

Snapshot-uri cumulative per report_date (retencție istorică); re-upload cu
același (source, report_date) înlocuiește doar acel snapshot.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e3f2a1b5d4"
down_revision: Union[str, None] = "b2e5a94cfd01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("client", sa.String(length=255), nullable=False),
        sa.Column("client_code", sa.String(length=100), nullable=True),
        sa.Column("ship_to", sa.String(length=255), nullable=True),
        sa.Column("chain", sa.String(length=100), nullable=True),
        sa.Column("nr_comanda", sa.String(length=100), nullable=True),
        sa.Column("product_code", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("category_code", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("remaining_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("remaining_quantity", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("data_livrare", sa.String(length=20), nullable=True),
        sa.Column("ind", sa.String(length=100), nullable=True),
        sa.Column("has_ind", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("store_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_orders_tenant_id", "raw_orders", ["tenant_id"])
    op.create_index("ix_raw_orders_batch_id", "raw_orders", ["batch_id"])
    op.create_index("ix_raw_orders_source", "raw_orders", ["source"])
    op.create_index("ix_raw_orders_report_date", "raw_orders", ["report_date"])
    op.create_index("ix_raw_orders_year_month", "raw_orders", ["year", "month"])
    op.create_index("ix_raw_orders_client", "raw_orders", ["client"])
    op.create_index("ix_raw_orders_client_code", "raw_orders", ["client_code"])
    op.create_index("ix_raw_orders_status", "raw_orders", ["status"])
    op.create_index("ix_raw_orders_store_id", "raw_orders", ["store_id"])
    op.create_index("ix_raw_orders_agent_id", "raw_orders", ["agent_id"])
    op.create_index("ix_raw_orders_product_id", "raw_orders", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_raw_orders_product_id", table_name="raw_orders")
    op.drop_index("ix_raw_orders_agent_id", table_name="raw_orders")
    op.drop_index("ix_raw_orders_store_id", table_name="raw_orders")
    op.drop_index("ix_raw_orders_status", table_name="raw_orders")
    op.drop_index("ix_raw_orders_client_code", table_name="raw_orders")
    op.drop_index("ix_raw_orders_client", table_name="raw_orders")
    op.drop_index("ix_raw_orders_year_month", table_name="raw_orders")
    op.drop_index("ix_raw_orders_report_date", table_name="raw_orders")
    op.drop_index("ix_raw_orders_source", table_name="raw_orders")
    op.drop_index("ix_raw_orders_batch_id", table_name="raw_orders")
    op.drop_index("ix_raw_orders_tenant_id", table_name="raw_orders")
    op.drop_table("raw_orders")
