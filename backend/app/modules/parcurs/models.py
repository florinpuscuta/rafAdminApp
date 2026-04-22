"""
Models pentru "Foaia de Parcurs" — o foaie per agent × lună × an cu
entries pe zi (rută, km, combustibil).

Schema urmează logica legacy: `travel_sheets` (meta) + `travel_sheet_entries`
(1 rând per zi lucrătoare). Alimentările cu combustibil sunt stocate inline
în `travel_sheet_fuel_fills` pentru auditabilitate.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class TravelSheet(Base):
    """
    Foaia de parcurs consolidată — o singură foaie per (tenant, scope, agent, year, month).
    Re-generate overwrite (upsert).
    """

    __tablename__ = "travel_sheets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "scope", "agent_name", "year", "month",
            name="uq_travel_sheets_tenant_scope_agent_period",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="adp")
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    car_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sediu: Mapped[str] = mapped_column(String(100), nullable=False, default="Oradea")
    km_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    km_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_km: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_km_per_day: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_fuel_liters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    total_fuel_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    entries: Mapped[list["TravelSheetEntry"]] = relationship(
        back_populates="sheet",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    fuel_fills: Mapped[list["TravelSheetFuelFill"]] = relationship(
        back_populates="sheet",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TravelSheetEntry(Base):
    """Un rând dintr-o foaie — o zi lucrătoare cu rută + km."""

    __tablename__ = "travel_sheet_entries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    sheet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("travel_sheets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_name: Mapped[str] = mapped_column(String(16), nullable=False)
    route: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    stores_visited: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # comma-sep
    km_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    km_end: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    km_driven: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    fuel_liters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    fuel_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    sheet: Mapped[TravelSheet] = relationship(back_populates="entries")


class TravelSheetFuelFill(Base):
    """Alimentare combustibil (bon fiscal) atașată unei foi."""

    __tablename__ = "travel_sheet_fuel_fills"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    sheet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("travel_sheets.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    fill_date: Mapped[date] = mapped_column(Date, nullable=False)
    liters: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    sheet: Mapped[TravelSheet] = relationship(back_populates="fuel_fills")
