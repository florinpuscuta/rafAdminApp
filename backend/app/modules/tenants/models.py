"""Organization model — entitatea de top-level a app-ului.

Tabelul a fost redenumit `tenants` → `organizations` in Faza 1 a planului de
normalizare. Pastram alias `Tenant = Organization` pentru codul existent
care importa `Tenant` (auth, audit etc) — va fi redenumit gradual.
"""
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class OrganizationKind(str, Enum):
    PRODUCTION = "production"
    DEMO = "demo"
    TEST = "test"


# Type Postgres reused by alembic; create_type=False ca sa nu incerce
# CREATE la metadata.create_all (l-a creat migrarea).
_organization_kind_pg = PG_ENUM(
    OrganizationKind, name="organization_kind", create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    kind: Mapped[OrganizationKind] = mapped_column(
        _organization_kind_pg, nullable=False, default=OrganizationKind.PRODUCTION,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )


# Alias backward-compat — codul existent foloseste `Tenant`. Va fi redenumit
# treptat in modulele care il importa.
Tenant = Organization
