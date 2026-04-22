"""add activitate + parcurs + probleme tables

Revision ID: 5f997fdb7a15
Revises: c7e3f2a1b5d4
Create Date: 2026-04-20 16:27:13.138152

Tabele pentru 3 module feature:
- `agent_visits` (activitate): vizite teren per agent × zi
- `travel_sheets` + `travel_sheet_entries` + `travel_sheet_fuel_fills`
  (parcurs): foaie de parcurs consolidată per agent × lună × an + rânduri pe zi
- `activity_problems` (probleme): text liber per (tenant, scope, year, month)

Notă: autogen-ul detectează și tabelele `tasks`/`task_assignments` din modulul
`taskuri` (models există deja dar nu e migrare) + un drop al unui index
compozit `ix_raw_orders_year_month`. Pentru a menține scope-ul strict al
acestei migrări (3 feature-uri listate), cele 3 de mai sus au fost excluse
manual. Taskuri-le vor primi propria migrare separată.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5f997fdb7a15'
down_revision: Union[str, None] = 'c7e3f2a1b5d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── activity_problems ──────────────────────────────────
    op.create_table(
        'activity_problems',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'scope', 'year', 'month',
            name='uq_activity_problems_tenant_scope_period',
        ),
    )
    op.create_index('ix_activity_problems_scope', 'activity_problems', ['scope'])
    op.create_index('ix_activity_problems_tenant_id', 'activity_problems', ['tenant_id'])

    # ── agent_visits ───────────────────────────────────────
    op.create_table(
        'agent_visits',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('visit_date', sa.Date(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=True),
        sa.Column('store_id', sa.UUID(), nullable=True),
        sa.Column('client', sa.String(length=255), nullable=True),
        sa.Column('check_in', sa.String(length=32), nullable=True),
        sa.Column('check_out', sa.String(length=32), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=True),
        sa.Column('km', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_visits_agent_id', 'agent_visits', ['agent_id'])
    op.create_index('ix_agent_visits_scope', 'agent_visits', ['scope'])
    op.create_index('ix_agent_visits_store_id', 'agent_visits', ['store_id'])
    op.create_index('ix_agent_visits_tenant_id', 'agent_visits', ['tenant_id'])
    op.create_index('ix_agent_visits_visit_date', 'agent_visits', ['visit_date'])

    # ── travel_sheets + entries + fuel_fills ──────────────
    op.create_table(
        'travel_sheets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=True),
        sa.Column('agent_name', sa.String(length=255), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('car_number', sa.String(length=32), nullable=True),
        sa.Column('sediu', sa.String(length=100), nullable=False),
        sa.Column('km_start', sa.Integer(), nullable=False),
        sa.Column('km_end', sa.Integer(), nullable=False),
        sa.Column('total_km', sa.Integer(), nullable=False),
        sa.Column('working_days', sa.Integer(), nullable=False),
        sa.Column('avg_km_per_day', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total_fuel_liters', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('total_fuel_cost', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('ai_generated', sa.Boolean(), nullable=False),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.text('now()'), nullable=False,
        ),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id', 'scope', 'agent_name', 'year', 'month',
            name='uq_travel_sheets_tenant_scope_agent_period',
        ),
    )
    op.create_index('ix_travel_sheets_agent_id', 'travel_sheets', ['agent_id'])
    op.create_index('ix_travel_sheets_scope', 'travel_sheets', ['scope'])
    op.create_index('ix_travel_sheets_tenant_id', 'travel_sheets', ['tenant_id'])

    op.create_table(
        'travel_sheet_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sheet_id', sa.UUID(), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('day_name', sa.String(length=16), nullable=False),
        sa.Column('route', sa.String(length=500), nullable=False),
        sa.Column('stores_visited', sa.String(length=1000), nullable=True),
        sa.Column('km_start', sa.Integer(), nullable=False),
        sa.Column('km_end', sa.Integer(), nullable=False),
        sa.Column('km_driven', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=255), nullable=False),
        sa.Column('fuel_liters', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('fuel_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.ForeignKeyConstraint(['sheet_id'], ['travel_sheets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_travel_sheet_entries_sheet_id', 'travel_sheet_entries', ['sheet_id'])

    op.create_table(
        'travel_sheet_fuel_fills',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('sheet_id', sa.UUID(), nullable=False),
        sa.Column('fill_date', sa.Date(), nullable=False),
        sa.Column('liters', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['sheet_id'], ['travel_sheets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_travel_sheet_fuel_fills_sheet_id', 'travel_sheet_fuel_fills', ['sheet_id'])


def downgrade() -> None:
    op.drop_index('ix_travel_sheet_fuel_fills_sheet_id', table_name='travel_sheet_fuel_fills')
    op.drop_table('travel_sheet_fuel_fills')
    op.drop_index('ix_travel_sheet_entries_sheet_id', table_name='travel_sheet_entries')
    op.drop_table('travel_sheet_entries')
    op.drop_index('ix_travel_sheets_tenant_id', table_name='travel_sheets')
    op.drop_index('ix_travel_sheets_scope', table_name='travel_sheets')
    op.drop_index('ix_travel_sheets_agent_id', table_name='travel_sheets')
    op.drop_table('travel_sheets')
    op.drop_index('ix_agent_visits_visit_date', table_name='agent_visits')
    op.drop_index('ix_agent_visits_tenant_id', table_name='agent_visits')
    op.drop_index('ix_agent_visits_store_id', table_name='agent_visits')
    op.drop_index('ix_agent_visits_scope', table_name='agent_visits')
    op.drop_index('ix_agent_visits_agent_id', table_name='agent_visits')
    op.drop_table('agent_visits')
    op.drop_index('ix_activity_problems_tenant_id', table_name='activity_problems')
    op.drop_index('ix_activity_problems_scope', table_name='activity_problems')
    op.drop_table('activity_problems')
