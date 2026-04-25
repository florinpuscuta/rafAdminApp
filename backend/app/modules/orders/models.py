from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RawOrder(Base):
    """
    Linie de comandă open, brut, din upload Excel (ADP radComenzi sau Sika).

    `source`: 'adp' sau 'sika' — discriminator pentru parser/UI.
    `report_date`: data snapshot-ului (cumulative; re-upload cu aceeași dată
      înlocuiește doar acel snapshot).
    `status`: 'NELIVRAT' | 'NEFACTURAT' (ADP) sau 'OPEN' (Sika).
    `remaining_*`: doar ADP (cant_rest / suma_rest proporțional).
    `ind`, `data_livrare`, `nr_comanda`: doar ADP.
    FK-uri (store_id/agent_id/product_id) se populează prin backfill după
    insert, identic cu raw_sales.
    """

    __tablename__ = "raw_orders"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    client: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ship_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nr_comanda: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    remaining_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    remaining_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    data_livrare: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ind: Mapped[str | None] = mapped_column(String(100), nullable=True)
    has_ind: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    store_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
