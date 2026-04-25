"""
Branduri de produs (tenant-scoped). Exemple Adeplast: "Adeplast" (propriu),
"Baumit" (competitor), "Hornbach Private Label" (is_private_label=True).

Flag-ul `is_private_label` înlocuiește magic string-ul "M_PRIVATA" din
app-ul legacy — queries pentru private label filtrează pe flag, nu pe nume.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Brand(Base):
    """
    Brand canonic tenant-scoped.
    """

    __tablename__ = "brands"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_brands_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_private_label: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BrandAlias(Base):
    """
    Mapping raw-string brand (cum apare în Excel) → Brand canonic.
    """

    __tablename__ = "brand_aliases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "raw_value", name="uq_brand_aliases_tenant_rawvalue",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_value: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolved_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
