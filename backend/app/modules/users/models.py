from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserRole(str, Enum):
    """Role canonice in app — corespund tipului user_role din Postgres."""
    ADMIN = "admin"
    DIRECTOR = "director"
    FINANCE_MANAGER = "finance_manager"
    REGIONAL_MANAGER = "regional_manager"
    SALES_AGENT = "sales_agent"
    VIEWER = "viewer"


_user_role_pg = PG_ENUM(
    UserRole, name="user_role", create_type=False,
    values_callable=lambda enum: [e.value for e in enum],
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # `role` (legacy varchar) — admin / member. Va fi inlocuit de `role_v2`.
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    # `role_v2` (canonic enum) — folosit gradual de feature-urile noi.
    role_v2: Mapped[UserRole] = mapped_column(
        _user_role_pg, nullable=False, default=UserRole.VIEWER,
    )
    # Link optional la agentul canonic (pentru sales_agent / regional_manager).
    agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    totp_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class UserManagedAgent(Base):
    """Asociere user (regional_manager) <-> agenti supravegheati.

    Folosita pentru filtrarea datelor: un manager regional vede doar
    vanzarile / magazinele agentilor lui.
    """
    __tablename__ = "user_managed_agents"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
