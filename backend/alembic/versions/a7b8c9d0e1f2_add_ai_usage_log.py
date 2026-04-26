"""add_ai_usage_log

Adaugă tabelul `ai_usage_log` pentru tracking-ul utilizării AI per tenant
(tokens consumate + cost USD + latency).

Revision ID: a7b8c9d0e1f2
Revises: d4f8a1b6c9e2
Create Date: 2026-04-26 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "d4f8a1b6c9e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ai_usage_log_tenant_id", "ai_usage_log", ["tenant_id"]
    )
    op.create_index(
        "ix_ai_usage_log_user_id", "ai_usage_log", ["user_id"]
    )
    op.create_index(
        "ix_ai_usage_log_created_at", "ai_usage_log", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_created_at", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_user_id", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_tenant_id", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
