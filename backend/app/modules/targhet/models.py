from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TarghetGrowthPct(Base):
    """Procent de creștere per (tenant, year, month) pentru calcul target.

    Target luna X = prev_year × (1 + pct[X]/100). Valoare scope-less —
    aceeași pentru adp/sika/sikadp și pentru Zona Agent. Dacă rândul
    lipsește, fallback la `DEFAULT_TARGET_PCT = 10`.
    """

    __tablename__ = "targhet_growth_pct"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "year", "month", name="uq_targhet_growth_pct_tenant_ym",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=10)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
