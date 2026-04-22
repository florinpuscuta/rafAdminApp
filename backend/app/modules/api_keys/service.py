"""
API keys service. Format cheie: `ak_` + 40 char urlsafe. Se hashează (sha256)
și se stochează hash-ul. Prefix-ul (primele 12 caractere din raw) e afișat
în UI ca identificator non-sensitiv.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.api_keys.models import ApiKey

KEY_PREFIX = "ak_"


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _generate_raw() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


async def list_by_tenant(session: AsyncSession, tenant_id: UUID) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey)
        .where(ApiKey.tenant_id == tenant_id)
        .order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_by_id(
    session: AsyncSession, tenant_id: UUID, key_id: UUID
) -> ApiKey | None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    created_by_user_id: UUID,
    name: str,
) -> tuple[ApiKey, str]:
    """Returnează (ApiKey persistat, raw secret — afișat o singură dată)."""
    raw = _generate_raw()
    key = ApiKey(
        tenant_id=tenant_id,
        created_by_user_id=created_by_user_id,
        name=name,
        key_hash=_hash(raw),
        prefix=raw[:12],
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    return key, raw


async def revoke(session: AsyncSession, key: ApiKey) -> None:
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        await session.commit()


async def authenticate(session: AsyncSession, raw: str) -> ApiKey | None:
    """Găsește cheia validă pentru raw. Atinge last_used_at + commit."""
    if not raw or not raw.startswith(KEY_PREFIX):
        return None
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == _hash(raw))
    )
    key = result.scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        return None
    key.last_used_at = datetime.now(timezone.utc)
    await session.commit()
    return key
