"""Production price per product per scope (adp / sika).

Doua tabele:

  - `production_prices` — pret MEDIU activ per (tenant, scope, product).
    Folosit pe dashboard-ul "Marja pe Perioada" si ca FALLBACK in dashboard-ul
    lunar cand nu exista snapshot pentru luna respectiva.

  - `production_prices_monthly` — snapshot per (tenant, scope, product,
    year, month). Folosit de "Analiza Marja Lunara" pentru a urmari variatia
    instantanee a marjei.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductionPrice(Base):
    __tablename__ = "production_prices"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "product_id",
            name="uq_production_prices_tenant_scope_product",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    last_imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
    last_imported_filename: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )


class ProductionPriceMonthly(Base):
    """Snapshot pret productie pe o luna anume — sursa pentru "Analiza Marja
    Lunara". Cand lipseste pentru o luna data, dashboard-ul foloseste fallback
    pe `ProductionPrice` (medie) cu disclaimer.
    """

    __tablename__ = "production_prices_monthly"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "product_id", "year", "month",
            name="uq_production_prices_monthly_tenant_scope_product_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    last_imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
    last_imported_filename: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
