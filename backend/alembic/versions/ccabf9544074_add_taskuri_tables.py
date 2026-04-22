"""add_taskuri_tables

Creează `tasks` și `task_assignments` pentru feature-ul Taskuri.

NOTĂ: În mediul curent de dev tabelele pot exista deja (au fost create
ad-hoc înainte de migrare). Folosim `IF NOT EXISTS` pentru idempotență —
migrarea e sigură atât pe DB curate cât și pe cele existente.

Revision ID: ccabf9544074
Revises: 5f997fdb7a15
Create Date: 2026-04-20 16:27:26.462926

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'ccabf9544074'
down_revision: Union[str, None] = '5f997fdb7a15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status VARCHAR(32) NOT NULL DEFAULT 'TODO',
            priority VARCHAR(16) NOT NULL DEFAULT 'medium',
            due_date DATE NULL,
            created_by_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_tenant_id ON tasks (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_status ON tasks (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_priority ON tasks (priority);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_due_date ON tasks (due_date);")

    op.execute("""
        CREATE TABLE IF NOT EXISTS task_assignments (
            id UUID PRIMARY KEY,
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_task_assignments_task_agent UNIQUE (task_id, agent_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_assignments_task_id ON task_assignments (task_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_task_assignments_agent_id ON task_assignments (agent_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_assignments;")
    op.execute("DROP TABLE IF EXISTS tasks;")
