from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentCompensation(Base):
    """Pachetul salarial al unui agent (masterdata, per tenant).

    Un agent = cel mult un rând. Costurile fixe (salariu + telefon + diurnă)
    se aplică direct lunar. `consum_l_100km` și `pret_carburant_ron_l` se
    combină cu `AgentMonthInput.km` la calculul costurilor variabile.
    """

    __tablename__ = "agent_compensation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_id", name="uq_agent_comp_tenant_agent"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    salariu_fix: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    bonus_vanzari_eligibil: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    telefon_flat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    diurna_flat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    consum_l_100km: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    pret_carburant_ron_l: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AgentMonthInput(Base):
    """Input lunar per agent: costurile variabile introduse manual în RON.

    Unique (tenant, agent, year, month) — o singură înregistrare per lună.
    Toate costurile (merchandiser, auto, alte cheltuieli) se introduc direct
    ca sume în RON. `alte_cheltuieli_label` e text liber pentru eticheta
    cheltuielii diverse. `km` și `pret_carburant_ron_l_snapshot` sunt legacy.
    """

    __tablename__ = "agent_month_inputs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "agent_id", "year", "month",
            name="uq_agent_month_inputs_tenant_agent_ym",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    # Costuri lunare directe (RON) — introduse manual
    merchandiser_zona_ron: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cheltuieli_auto_ron: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    alte_cheltuieli_ron: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    alte_cheltuieli_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Legacy (unused) — păstrate ca să nu rupem schema existentă
    km: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    pret_carburant_ron_l_snapshot: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3), nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AgentStoreBonus(Base):
    """Bonus lunar manual, per (agent, magazin, lună).

    Sursă pentru "Bonus zonă" din matricea lunară a agentului: suma pe
    toate magazinele agentului pentru luna respectivă.
    """

    __tablename__ = "agent_store_bonus"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "agent_id", "store_id", "year", "month",
            name="uq_agent_store_bonus_tenant_agent_store_ym",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FacturiBonusDecision(Base):
    """Decizie persistentă pentru o factură bonus: se ține pe (tenant, year,
    month, client, amount) — combinație stabilă între re-import-uri, spre
    deosebire de raw_sale.id care se schimbă la fiecare refresh de date.

    Rolul: după ce o factură < threshold e reasignată (fie automat prin
    regula KA, fie manual prin meniu), scriem aici decizia ca să nu mai apară
    ca "de asignat" la următorul import. Permite și "dezasignează" (dacă
    ștergem decizia, factura revine ca pending).

    `source`: 'auto' (regula KA aplicată la import) sau 'manual' (user a
    apăsat accept în meniu).
    """

    __tablename__ = "facturi_bonus_decisions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "year", "month", "client", "amount",
            name="uq_facturi_bonus_decisions_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    client: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    target_agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="auto")
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StoreContactBonus(Base):
    """Bonus lunar plătit unui "om de raion" dintr-un magazin.

    Un magazin poate avea mai mulți contact-persons într-o lună, deci NU e
    unique pe (store, year, month). Agentul se deduce din alocarea
    magazin→agent existentă; păstrăm și aici un `agent_id` pentru raportare
    rapidă și pentru cazul în care alocarea se schimbă ulterior (istoric).
    """

    __tablename__ = "store_contact_bonus"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    suma: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
