"""
Public service pentru modulul `tenants`.
Alte module folosesc doar funcțiile declarate aici; nu se importă direct `models`.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.models import Tenant


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "tenant"


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Tenant.id).where(Tenant.slug == slug))
    return result.scalar_one_or_none() is not None


async def create_tenant(session: AsyncSession, name: str) -> Tenant:
    base_slug = _slugify(name)
    slug = base_slug
    suffix = 2
    while await slug_exists(session, slug):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    tenant = Tenant(name=name, slug=slug)
    session.add(tenant)
    await session.flush()
    return tenant


async def get_by_id(session: AsyncSession, tenant_id) -> Tenant | None:
    return await session.get(Tenant, tenant_id)


async def update_tenant(
    session: AsyncSession, tenant: Tenant, *, name: str | None = None
) -> Tenant:
    if name is not None and name != tenant.name:
        tenant.name = name
    await session.commit()
    return tenant


async def soft_delete(session: AsyncSession, tenant: Tenant) -> None:
    """Soft-delete: setează active=false. Utilizatorii nu mai pot accesa (login
    verifică tenant.active)."""
    tenant.active = False
    await session.commit()
