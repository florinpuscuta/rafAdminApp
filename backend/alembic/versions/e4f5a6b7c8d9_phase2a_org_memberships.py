"""phase2a_org_memberships

Sub-faza 1 din planul "split Adpsika" — infrastructure multi-org membership.

Adauga tabel `user_organization_memberships` care leaga un user de N orgs.
Populeaza initial: fiecare user devine membru al organizatiei lui curente
din `users.tenant_id`, cu `is_default=true` si `role` = `users.role_v2`.

`users.tenant_id` ramane in tabel ca "default org" (legacy + fallback).
Switch-ul activ se face stateless: clientul trimite header `X-Active-Org-Id`,
validat in dep contra membership.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-04-25 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_organization_memberships (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            role_v2 user_role NOT NULL DEFAULT 'viewer',
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, organization_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_org_memberships_org "
        "ON user_organization_memberships(organization_id)"
    )

    # Garantam ca un user are EXACT un is_default=true.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_org_default "
        "ON user_organization_memberships(user_id) WHERE is_default = TRUE"
    )

    # Populare initiala: fiecare user e membru al organizatiei lui curente
    # cu is_default=true si role copiat din users.role_v2.
    op.execute("""
        INSERT INTO user_organization_memberships (
            user_id, organization_id, role_v2, is_default, joined_at
        )
        SELECT u.id, u.tenant_id, u.role_v2, TRUE, NOW()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM user_organization_memberships m
            WHERE m.user_id = u.id AND m.organization_id = u.tenant_id
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_organization_memberships")
