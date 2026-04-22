"""
Models pentru "Acțiuni SIKA" (marketing) — port 1:1 al tabelului legacy
`marketing_actions` din `adeplast-dashboard/services/db.py` + `routes/sales.py`.

Legacy:
    CREATE TABLE IF NOT EXISTS marketing_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        updated_by TEXT DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now')),
        UNIQUE(year, month)
    )

SaaS: adăugăm `tenant_id` + `scope` în cheia unică (scope default = "sika",
identic cu semantica legacy — marketing_actions era folosit *doar* în
ecranul "Actiuni Sika" sub SIKADP). Păstrăm UUID PK + timezone-aware
timestamps.

Pozele sunt gestionate prin modulul `gallery` existent:
folder `type='sika'`, `name=f'{year}-{month:02d}'` — oglinde├â directă
a convenției legacy `uploads/actiuni_sika/YYYY-MM/`.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MarketingAction(Base):
    """Text liber "Acțiuni SIKA" pentru (tenant, scope, year, month). Upsert."""

    __tablename__ = "marketing_actions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "year", "month",
            name="uq_marketing_actions_tenant_scope_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="sika")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
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
