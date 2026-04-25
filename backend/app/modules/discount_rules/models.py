"""Reguli de discount per (client KA, scope, grupa).

Default implicit (lipsa unei reguli) = `applies = TRUE` — clientul ofera
discount-ul retro (cota din storno) pe acea grupa. Inseram explicit doar
randurile cu `applies = FALSE` cand o grupa NU primeste cota.

Cheia `group_kind`:
  - 'category'        → group_key = ProductCategory.code (EPS, MU, ...)
  - 'private_label'   → group_key = 'marca_privata' (singleton — Marca Privata
                        agregata indiferent de categorie)
  - 'tm'              → group_key = TM Sika (Building Finishing, ...)
                        rezervat pentru scope='sika' in faza ulterioara

Pentru scope='adp' grupele afisate in matrix sunt categoriile + 'Marca Privata'
ca rand separat. Aceasta separare reflecta logica businessului: la Dedeman /
Hornbach, EPS si Marca Privata NU primesc discount, dar restul categoriilor da.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DiscountRule(Base):
    __tablename__ = "discount_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "client_canonical", "scope",
            "group_kind", "group_key",
            name="uq_discount_rules_tenant_client_scope_group",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    client_canonical: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    group_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    group_key: Mapped[str] = mapped_column(String(100), nullable=False)
    applies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
