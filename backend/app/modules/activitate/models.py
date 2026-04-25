"""
Models pentru "Activitate Agenți" — vizite teren loguite per agent/zi.

Un `AgentVisit` = un check-in la un magazin într-o zi. Include durată, km
parcurși, notițe. FK-uri canonice către `agents` și `stores` (tenant-scoped).

În legacy nu exista un tabel dedicat — era derivat din photos + panels. În
SaaS facem tabel explicit ca să permitem înregistrare manuală + import ulterior.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentVisit(Base):
    """
    O vizită a unui agent la un magazin într-o zi.

    `scope`: 'adp' | 'sika' | 'sikadp' — pentru company switcher. Nu FK,
      e un discriminator simplu (aceeași logică ca alte module).
    `duration_min`: opțional, calculabil din check_in/check_out dar
      persistat pentru raportare rapidă.
    """

    __tablename__ = "agent_visits"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="adp")
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    client: Mapped[str | None] = mapped_column(String(255), nullable=True)
    check_in: Mapped[str | None] = mapped_column(String(32), nullable=True)   # HH:MM sau ISO ts
    check_out: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
