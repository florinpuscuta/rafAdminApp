"""App settings — key/value persistent storage per tenant.

Echivalent cu legacy `app_settings` din `users.db` — stochează chei AI
(anthropic/openai/xai), flags, preferințe. Accesibil din tot SaaS-ul.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, PrimaryKeyConstraint, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "key", name="pk_app_settings"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )
