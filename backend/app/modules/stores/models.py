from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Store(Base):
    """
    Magazin canonic (ex: "DEDEMAN București Pipera"). Tenant-scoped.
    Stringuri brute din `raw_sales.client` se leagă de Store prin StoreAlias.
    """

    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_stores_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StoreAlias(Base):
    """
    Mapping-ul unui string brut (din Excel) la un Store canonic.
    Tenant-scoped. Un raw_client unic per tenant — primul care se mapează câștigă.
    Păstrăm who/when pentru audit.
    """

    __tablename__ = "store_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "raw_client", name="uq_store_aliases_tenant_rawclient"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_client: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    store_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
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
