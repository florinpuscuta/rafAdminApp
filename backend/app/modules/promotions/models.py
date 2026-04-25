"""Modele promotii — definitie + tinte (produse / categorii / TM / PL / all).

Promotia descrie o reducere de pret aplicata pe o selectie de produse, la
clienti KA selectati, intr-o fereastra calendaristica. Folosita pentru
simulari de impact pe marja (baseline YoY sau perioada anterioara).
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Promotion(Base):
    __tablename__ = "promotions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", index=True,
    )  # 'draft' | 'active' | 'archived'
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'pct'             — value e procent (0..100), aplicat pe revenue/unit
    # 'override_price'  — value e pret RON pe unitate (inlocuieste pretul curent)
    # 'fixed_per_unit'  — value e suma RON scazuta din pret la fiecare unitate
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    # client_filter: lista de client_canonical (ex: ["DEDEMAN SRL", "LEROY MERLIN ROMANIA SRL"])
    # null sau lista goala = se aplica la toti clientii KA
    client_filter: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # manual_quantities: {product_id_str: qty_decimal_str} — estimari editate de
    # user pentru simulare. Lipsa cheii = se foloseste cantitatea baseline (YoY/MoM).
    # Folosim string pentru qty ca sa pastram precizia (Decimal -> str -> Decimal).
    manual_quantities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class PromotionTarget(Base):
    __tablename__ = "promotion_targets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    promotion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'product' (key=Product.code), 'category' (key=ProductCategory.code),
    # 'tm' (key=TM label), 'private_label' (key='marca_privata'),
    # 'all' (key=ignored)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
