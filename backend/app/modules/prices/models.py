"""
Modele pentru "Prețuri Comparative" + "Adeplast/Sika cross-KA" — port 1:1 din
legacy `adeplast-dashboard/routes/pricing.py` (tabele `price_grid`,
`price_grid_meta`).

Legacy schemas (SQLite, per-company DB — izolare prin DB-uri separate):
    price_grid (id PK, store TEXT, row_idx INT, row_num TEXT, group_label TEXT,
                brand_data JSON, imported_at TEXT, import_source TEXT, company TEXT)

    price_grid_meta (store TEXT PK, date_prices TEXT, brands JSON,
                     imported_at TEXT, imported_by TEXT, company TEXT)

Adaptări SaaS:
  - UUID PK (în loc de INTEGER AUTOINCREMENT)
  - tenant_id + company — izolare pe tenant × companie (ADP / SIKA)
  - brand_data / brands stocate ca JSONB (nativ Postgres, indexabil)
  - legacy_id pentru import
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PriceGridRow(Base):
    """Un rând din grid-ul Preturi Comparative (o linie Excel per produs)."""

    __tablename__ = "price_grid"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "company", "store", "row_idx",
            name="uq_price_grid_tenant_company_store_row",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(
        String(20), nullable=False, default="adeplast", index=True,
    )
    store: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    row_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    row_num: Mapped[str | None] = mapped_column(String(50), nullable=True)
    group_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Structura: { "BRAND_NAME": {"prod": str, "pret": float, "ai_status"?, "ai_url"?, ...}, ... }
    brand_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    import_source: Mapped[str] = mapped_column(String(50), nullable=False, default="excel")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class PriceUpdateJob(Base):
    """Job AI pentru actualizarea prețurilor — port 1:1 din legacy
    `users.db.price_update_jobs` (services/price_update_service.py:62-79).
    """

    __tablename__ = "price_update_jobs"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company: Mapped[str] = mapped_column(String(20), nullable=False, default="adeplast")
    store: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending | running | done | failed | cancelled
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)


class PriceGridMeta(Base):
    """Meta per store: data prețurilor, lista brandurilor, autor."""

    __tablename__ = "price_grid_meta"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "company", "store", name="pk_price_grid_meta"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company: Mapped[str] = mapped_column(String(20), nullable=False)
    store: Mapped[str] = mapped_column(String(80), nullable=False)
    date_prices: Mapped[str | None] = mapped_column(String(30), nullable=True)
    brands: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    imported_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
