"""
Modele pentru Panouri & Standuri — port 1:1 al feature-ului din
`adeplast-dashboard/routes/gallery.py` (tabel `panouri_standuri`).

Legacy schema (SQLite):
    CREATE TABLE panouri_standuri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_name TEXT NOT NULL,
        panel_type TEXT NOT NULL DEFAULT 'panou',
        title TEXT,
        width_cm REAL,
        height_cm REAL,
        location_in_store TEXT,
        notes TEXT,
        photo_filename TEXT,
        photo_thumb TEXT,
        agent TEXT,
        created_by TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )

Adaptări SaaS:
  - UUID primary key (în loc de INTEGER AUTOINCREMENT)
  - tenant_id obligatoriu (izolare multi-tenant)
  - store_name rămâne TEXT liber (legacy folosea `cheie_finala` din
    unified_store_agent_map ca identificator opac — noi folosim stores.name)
  - Tipuri exacte: panel_type TEXT, width_cm/height_cm REAL(Float), created_by TEXT
  - `legacy_id` păstrat pentru import din users.db
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PanouStand(Base):
    """Panou publicitar sau stand de expunere înregistrat la un magazin.

    Oglindire 1:1 a legacy `panouri_standuri`.
    """

    __tablename__ = "panouri_standuri"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Textual key — legacy folosea `cheie_finala` din unified_store_agent_map.
    # În SaaS păstrăm tot TEXT (nume magazin opac) pentru paritate cu UI-ul.
    store_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # 'panou' | 'stand' | 'totem' | 'banner' | 'gondola' | 'altele'
    panel_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="panou", index=True
    )
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    width_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_in_store: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Câmpuri photo_filename/photo_thumb din legacy — rămân pentru paritate, dar
    # în SaaS fotografiile sunt stocate în tabela `gallery_photos` (MinIO).
    photo_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_thumb: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agent: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Păstrat pentru import din users.db legacy.
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
