from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Product(Base):
    """
    Produs canonic (SKU). Tenant-scoped. raw_sales.product_code e string brut
    care se leagă prin ProductAlias.

    Canonical: `category_id` → product_categories (global), `brand_id` →
    brands (tenant-scoped). String-urile vechi `category` / `brand` rămân
    populate în paralel pentru safety pe perioada migrării — queries noi
    folosesc FK-urile, nu string-urile.
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_products_tenant_code"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    # Legacy string columns — populate în paralel cu FK-urile; vor fi DROP
    # după ce toate feature-urile trec pe canonical (safety migration).
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Canonical FK-uri (noi — nullable ca să nu spargem rânduri existente).
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductAlias(Base):
    """
    Mapping raw_code (din Excel) la Product canonic. Unic per tenant.
    Mai multe alias-uri pot pointa la același Product (SKU multiple per produs).
    """

    __tablename__ = "product_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "raw_code", name="uq_product_aliases_tenant_rawcode"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
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
