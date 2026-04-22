"""
Models pentru "Probleme în Activitate" — conținut text liber + poze per
(tenant, scope, year, month).

Legacy folosea `activity_problems` cu UNIQUE(year, month). Aici adăugăm
tenant_id + scope în cheia unică.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ActivityProblem(Base):
    """Text liber de probleme pentru (tenant, scope, year, month). Upsert."""

    __tablename__ = "activity_problems"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "year", "month",
            name="uq_activity_problems_tenant_scope_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="adp")
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
