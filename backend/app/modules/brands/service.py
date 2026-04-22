"""
Service pentru `brands` (tenant-scoped) + alias-uri. Pattern identic cu
stores/agents/products — rezolvare raw→canonical prin alias tables.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brands.models import Brand, BrandAlias


async def list_by_tenant(session: AsyncSession, tenant_id: UUID) -> list[Brand]:
    stmt = (
        select(Brand)
        .where(Brand.tenant_id == tenant_id)
        .order_by(Brand.sort_order, Brand.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_by_name(
    session: AsyncSession, tenant_id: UUID, name: str
) -> Brand | None:
    stmt = select(Brand).where(Brand.tenant_id == tenant_id, Brand.name == name)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    is_private_label: bool = False,
    sort_order: int = 0,
) -> Brand:
    brand = Brand(
        tenant_id=tenant_id,
        name=name,
        is_private_label=is_private_label,
        sort_order=sort_order,
    )
    session.add(brand)
    await session.flush()
    return brand


async def resolve_map(
    session: AsyncSession, tenant_id: UUID, raw_values: list[str]
) -> dict[str, UUID]:
    """{raw_value: brand_id} pentru cele cu alias existent."""
    if not raw_values:
        return {}
    stmt = (
        select(BrandAlias.raw_value, BrandAlias.brand_id)
        .where(
            BrandAlias.tenant_id == tenant_id,
            BrandAlias.raw_value.in_(raw_values),
        )
    )
    result = await session.execute(stmt)
    return {raw: bid for raw, bid in result.all()}


async def create_alias(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    raw_value: str,
    brand_id: UUID,
    resolved_by_user_id: UUID | None = None,
) -> BrandAlias:
    alias = BrandAlias(
        tenant_id=tenant_id,
        raw_value=raw_value,
        brand_id=brand_id,
        resolved_by_user_id=resolved_by_user_id,
    )
    session.add(alias)
    await session.flush()
    return alias
