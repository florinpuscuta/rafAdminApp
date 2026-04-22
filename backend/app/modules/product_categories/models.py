"""
Catalog global de categorii de produse standardizate în SaaS
(EPS, MU, UMEDE, VARSACI). Codurile sunt fixe la nivel SaaS — toate
tenant-urile referă aceleași rânduri.

Alias-urile către raw-strings din Excel sunt tenant-scoped (fiecare client
poate scrie categoriile diferit în fișierele lui).
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProductCategory(Base):
    """
    Categorie globală de produs (nu are tenant_id). Seed fix la migration
    — EPS, MU, UMEDE, VARSACI pentru verticala materiale construcții.
    """

    __tablename__ = "product_categories"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductCategoryAlias(Base):
    """
    Mapping raw-string (cum scrie user-ul în Excel) → ProductCategory global.
    Tenant-scoped: fiecare tenant are propriul set de alias-uri.
    """

    __tablename__ = "product_category_aliases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "raw_value",
            name="uq_product_category_aliases_tenant_rawvalue",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_value: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="CASCADE"),
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
