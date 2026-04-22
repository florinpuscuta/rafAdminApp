"""Modele pentru Taskuri.

Inspirate din legacy (`adeplast-dashboard/services/db.py` — tabele `tasks`
și `task_assignments`) dar re-gandite pentru SaaS:
  - Tenant-scoped (UUID PK, tenant_id FK → tenants.id).
  - `status` enum explicit (TODO / IN_PROGRESS / DONE) în loc de flag `active`.
  - `priority` (low / medium / high) înlocuiește `urgency` din legacy.
  - `due_date` în loc de `(year, month)` — granularitate zilnică, flexibilă.
  - Asignarea rămâne many-to-one pe Agent (un task poate avea mulți agenți
    responsabili), fără read_at/completed_at — pentru V1 e suficient ca
    status-ul să trăiască pe Task; detaliu per-agent se poate adăuga ulterior.
"""
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Task(Base):
    """Un task creat de un user (manager/admin), cu status + prioritate."""

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")

    # TODO | IN_PROGRESS | DONE — string simplu, validat la nivel de schemă
    # Pydantic; nu folosim Enum SQLAlchemy ca să evităm migrații grele când
    # adăugăm stări noi (CANCELLED, BLOCKED, etc).
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="TODO", server_default="TODO", index=True,
    )
    # low | medium | high
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium", index=True,
    )

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )


class TaskAssignment(Base):
    """Legătură task ↔ agent. Un task poate fi asignat mai multor agenți;
    un agent poate avea multe taskuri. UNIQUE (task_id, agent_id) previne
    duplicate.
    """

    __tablename__ = "task_assignments"
    __table_args__ = (
        UniqueConstraint("task_id", "agent_id", name="uq_task_assignments_task_agent"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
