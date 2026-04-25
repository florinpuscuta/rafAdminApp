"""phase4_audit_fields

Adauga audit fields lipsa pe tabelele recent introduse:
  - discount_rules: created_at, updated_at, updated_by_user_id
  - promotion_targets: created_at
  - agent_store_assignments: assigned_by_user_id

Tabelele *_aliases au deja `resolved_by_user_id`+`resolved_at` (echivalent
audit) — nu sunt atinse.

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-04-25 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # discount_rules: full audit
    op.execute(
        "ALTER TABLE discount_rules "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    )
    op.execute(
        "ALTER TABLE discount_rules "
        "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    )
    op.execute(
        "ALTER TABLE discount_rules "
        "ADD COLUMN IF NOT EXISTS updated_by_user_id UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )

    # promotion_targets: created_at (when target was added)
    op.execute(
        "ALTER TABLE promotion_targets "
        "ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
    )

    # agent_store_assignments: assigned_by_user_id
    op.execute(
        "ALTER TABLE agent_store_assignments "
        "ADD COLUMN IF NOT EXISTS assigned_by_user_id UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_store_assignments DROP COLUMN IF EXISTS assigned_by_user_id")
    op.execute("ALTER TABLE promotion_targets DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE discount_rules DROP COLUMN IF EXISTS updated_by_user_id")
    op.execute("ALTER TABLE discount_rules DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE discount_rules DROP COLUMN IF EXISTS created_at")
