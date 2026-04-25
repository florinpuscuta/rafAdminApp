"""
Sursa de adevăr pentru maparea (Client_Original, Ship_to_Original, Sursa)
→ (Magazin canonic, Agent canonic).

Alimentată din fișier extern "mapare_completa_magazine_cu_coduri_v2.xlsx"
(versiunea Raf). Înlocuiește logica bazată pe sheet-ul Alocare — fiind
sursă unificată pentru ADP + SIKA, elimină discrepanțele nume-agent.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StoreAgentMapping(Base):
    """
    Un rând = o mapare de la un raw (source, client, ship_to) la canonicalul
    unificat (cheie_finala → store, agent_unificat → agent).

    La upload, fiecare `cheie_finala` nouă creează un Store canonic nou
    (dacă nu există), iar fiecare `agent_unificat` nou creează un Agent.

    Câmpul `agent_original` și `cod_numeric` sunt păstrate pentru audit /
    debugging — nu sunt folosite activ în rezolvare.
    """

    __tablename__ = "store_agent_mappings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Sursa datelor raw: "ADP" (din Excel vânzări Adeplast) sau "SIKA" (din
    # cel Sika). Împreună cu client_original + ship_to_original formează
    # cheia naturală pentru rezolvare.
    source: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    client_original: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    ship_to_original: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_original: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cod_numeric: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Valorile canonice — sursa de adevăr.
    cheie_finala: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_unificat: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # FK către entitățile canonice, populate la ingest după get-or-create.
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source", "client_original", "ship_to_original",
            name="uq_store_agent_mappings_tenant_src_client_ship",
        ),
    )
