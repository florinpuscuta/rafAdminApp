"""
Public service pentru modulul `users`.
Alte module folosesc doar funcțiile declarate aici; nu se importă direct `models`.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.users.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def list_by_tenant(session: AsyncSession, tenant_id: UUID) -> list[User]:
    result = await session.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def create_user(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    email: str,
    password: str,
    role: str = "member",
) -> User:
    user = User(
        tenant_id=tenant_id,
        email=email.lower().strip(),
        password_hash=hash_password(password),
        role=role,
    )
    session.add(user)
    await session.flush()
    return user


async def touch_last_login(session: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    await session.flush()


async def update_password(session: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await session.flush()


async def record_failed_login(
    session: AsyncSession,
    user: User,
    *,
    max_attempts: int,
    lock_minutes: int,
) -> None:
    """Incrementă contorul. La `max_attempts` fail-uri, aplică lock temporar."""
    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= max_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
    await session.commit()


async def reset_failed_login(session: AsyncSession, user: User) -> None:
    """Reset contor + lock la login reușit."""
    user.failed_login_count = 0
    user.locked_until = None
    await session.flush()


async def set_totp_secret(
    session: AsyncSession, user: User, secret: str | None, enabled: bool
) -> None:
    user.totp_secret = secret
    user.totp_enabled = enabled
    await session.commit()


async def update_user(
    session: AsyncSession,
    user: User,
    *,
    role: str | None = None,
    active: bool | None = None,
) -> User:
    if role is not None:
        user.role = role
    if active is not None:
        user.active = active
        if not active:
            # dezactivare → deblochează dacă era locked (n-are sens să mai aibă lock)
            user.locked_until = None
    await session.commit()
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()
