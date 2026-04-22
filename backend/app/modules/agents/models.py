from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AgentStoreAssignment(Base):
    """Asignare explicită store ↔ agent (cine acoperă care magazin)."""

    __tablename__ = "agent_store_assignments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "agent_id", "store_id", name="uq_ag_st_tenant_ag_st"),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Agent(Base):
    """
    Agent canonic (persoana de vânzări). Tenant-scoped. String-urile
    `raw_sales.agent` sunt unificate la un Agent prin AgentAlias — asta
    înlocuiește fosta soluție cu `AGENT_FIXES = {...}` hardcoded în cod.
    """

    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "full_name", name="uq_agents_tenant_fullname"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentAlias(Base):
    """
    Mapping-ul unui string brut din Excel (`raw_sales.agent`) la un Agent canonic.
    Audit trail: cine a rezolvat, când. Mai multe alias-uri pot pointa la același
    Agent (util pentru tipouri: "Ionut FIlip" și "Ionut Filip" → același Agent).
    """

    __tablename__ = "agent_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "raw_agent", name="uq_agent_aliases_tenant_rawagent"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_agent: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
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
