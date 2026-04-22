"""
Service pentru catalog global `product_categories` + alias-uri tenant-scoped.

- `list_all()` — lista globală (identică pentru toți tenanții).
- `get_by_code()` — lookup rapid pentru query-uri (ex: EPS, MU).
- `resolve_map(tenant_id, raw_values)` — raw-string → category_id via
  `product_category_aliases`, aliniat cu pattern-ul din stores/agents/products.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.product_categories.models import (
    ProductCategory,
    ProductCategoryAlias,
)


async def list_all(session: AsyncSession) -> list[ProductCategory]:
    stmt = select(ProductCategory).order_by(
        ProductCategory.sort_order, ProductCategory.code
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_by_code(session: AsyncSession, code: str) -> ProductCategory | None:
    stmt = select(ProductCategory).where(ProductCategory.code == code.upper())
    return (await session.execute(stmt)).scalar_one_or_none()


async def resolve_map(
    session: AsyncSession, tenant_id: UUID, raw_values: list[str]
) -> dict[str, UUID]:
    """
    Returnează {raw_value: category_id} pentru raw-values care au deja alias.
    Valorile ne-mapate nu apar în dict (router-ul apelant decide ce face).
    """
    if not raw_values:
        return {}
    stmt = (
        select(ProductCategoryAlias.raw_value, ProductCategoryAlias.category_id)
        .where(
            ProductCategoryAlias.tenant_id == tenant_id,
            ProductCategoryAlias.raw_value.in_(raw_values),
        )
    )
    result = await session.execute(stmt)
    return {raw: cat_id for raw, cat_id in result.all()}


async def create_alias(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    raw_value: str,
    category_id: UUID,
    resolved_by_user_id: UUID | None = None,
) -> ProductCategoryAlias:
    alias = ProductCategoryAlias(
        tenant_id=tenant_id,
        raw_value=raw_value,
        category_id=category_id,
        resolved_by_user_id=resolved_by_user_id,
    )
    session.add(alias)
    await session.flush()
    return alias
