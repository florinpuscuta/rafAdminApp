"""phase1_organizations_user_roles

Faza 1 a planului de normalizare:
  - RENAME TABLE tenants -> organizations (FK-urile continua sa functioneze)
  - ADD organizations.kind ENUM('production','demo','test')
  - Marcheaza Test Verify / TestMobile ca 'test', Concurent SRL ca 'demo'
  - CREATE TYPE user_role ENUM
  - ADD users.role_v2 user_role (mapeaza admin->admin, member->viewer)
  - ADD users.agent_id UUID -> agents(id) ON DELETE SET NULL
  - CREATE TABLE user_managed_agents (asociere user-manager <-> agenti)

Coloanele `tenant_id` din celelalte 40+ tabele NU sunt redenumite (FK-urile
continua sa pointeze la tabelul `organizations` redenumit). Rename-ul de
coloana se va face intr-o sub-faza separata.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b8
Create Date: 2026-04-25 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename tabel + creeaza enum + adauga coloana kind
    op.execute("ALTER TABLE tenants RENAME TO organizations")
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE organization_kind AS ENUM ('production','demo','test'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS kind "
        "organization_kind NOT NULL DEFAULT 'production'"
    )

    # 2. Marcheaza tenant-urile non-productie pe baza numelui.
    op.execute(
        "UPDATE organizations SET kind = 'test' "
        "WHERE name IN ('Test Verify','TestMobile')"
    )
    op.execute(
        "UPDATE organizations SET kind = 'demo' "
        "WHERE name = 'Concurent SRL'"
    )

    # 3. Enum user_role
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE user_role AS ENUM ("
        "  'admin','director','finance_manager',"
        "  'regional_manager','sales_agent','viewer'"
        "); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_v2 "
        "user_role NOT NULL DEFAULT 'viewer'"
    )
    op.execute(
        "UPDATE users SET role_v2 = 'admin' WHERE role = 'admin'"
    )
    op.execute(
        "UPDATE users SET role_v2 = 'viewer' WHERE role = 'member'"
    )

    # 4. Link user -> agent canonic (1:1 optional)
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS agent_id UUID "
        "REFERENCES agents(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_agent_id ON users(agent_id)"
    )

    # 5. Tabel asociere user-manager <-> agenti supravegheati
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_managed_agents (
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, agent_id)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_managed_agents_agent_id "
        "ON user_managed_agents(agent_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_managed_agents")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS agent_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role_v2")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS kind")
    op.execute("DROP TYPE IF EXISTS organization_kind")
    op.execute("ALTER TABLE organizations RENAME TO tenants")
