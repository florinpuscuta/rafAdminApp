from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ImportBatch(Base):
    """
    Un upload Excel = un batch. Păstrează metadata (fișier, cine, când, câte
    rânduri inserate/ignorate) ca să putem audita / face rollback.
    """

    __tablename__ = "import_batches"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="sales_xlsx")
    inserted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RawSale(Base):
    """
    Linie individuală de vânzare, brut, provenită dintr-un import Excel.
    Tenant-scoped. String-urile originale (client, agent, product_name) sunt
    imuabile — rezolvarea către entități canonice (stores, agents, products)
    se va face mai târziu prin tabele de aliases, populând FK-uri nullable.
    """

    __tablename__ = "raw_sales"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    client: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Cod ship-to numeric (populat de importul Sika din col "Ship-to Party").
    # E stabil când numele magazinului variază între exporturi — folosit ca
    # match primar în backfill pentru source=SIKA, cu fallback pe client+ship-to.
    client_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    agent: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
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
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
