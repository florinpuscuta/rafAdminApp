"""
Public service pentru modulul `products`. Deține Product + ProductAlias.
NU atinge `raw_sales` — enrichment via contract din `sales.service`.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.products.models import Product, ProductAlias


async def list_products(session: AsyncSession, tenant_id: UUID) -> list[Product]:
    return await list_products_by_tenants(session, [tenant_id])


async def list_products_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[Product]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(Product)
        .where(Product.tenant_id.in_(tenant_ids))
        .order_by(Product.code)
    )
    return list(result.scalars().all())


async def get_product(
    session: AsyncSession, tenant_id: UUID, product_id: UUID
) -> Product | None:
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def create_product(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    code: str,
    name: str,
    category: str | None = None,
    brand: str | None = None,
) -> Product:
    product = Product(
        tenant_id=tenant_id, code=code, name=name, category=category, brand=brand
    )
    session.add(product)
    await session.flush()
    return product


async def list_aliases(session: AsyncSession, tenant_id: UUID) -> list[ProductAlias]:
    return await list_aliases_by_tenants(session, [tenant_id])


async def list_aliases_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[ProductAlias]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(ProductAlias)
        .where(ProductAlias.tenant_id.in_(tenant_ids))
        .order_by(ProductAlias.raw_code)
    )
    return list(result.scalars().all())


async def get_alias_by_raw(
    session: AsyncSession, tenant_id: UUID, raw_code: str
) -> ProductAlias | None:
    result = await session.execute(
        select(ProductAlias).where(
            ProductAlias.tenant_id == tenant_id,
            ProductAlias.raw_code == raw_code,
        )
    )
    return result.scalar_one_or_none()


async def create_alias(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    raw_code: str,
    product_id: UUID,
    resolved_by_user_id: UUID | None = None,
) -> ProductAlias:
    alias = ProductAlias(
        tenant_id=tenant_id,
        raw_code=raw_code,
        product_id=product_id,
        resolved_by_user_id=resolved_by_user_id,
    )
    session.add(alias)
    await session.flush()
    return alias


async def resolve_map(
    session: AsyncSession, tenant_id: UUID, raw_codes: list[str]
) -> dict[str, UUID]:
    if not raw_codes:
        return {}
    result = await session.execute(
        select(ProductAlias.raw_code, ProductAlias.product_id).where(
            ProductAlias.tenant_id == tenant_id,
            ProductAlias.raw_code.in_(raw_codes),
        )
    )
    return {row[0]: row[1] for row in result.all()}


async def get_alias_by_id(
    session: AsyncSession, tenant_id: UUID, alias_id: UUID
) -> ProductAlias | None:
    result = await session.execute(
        select(ProductAlias).where(
            ProductAlias.id == alias_id, ProductAlias.tenant_id == tenant_id
        )
    )
    return result.scalar_one_or_none()


async def delete_alias(session: AsyncSession, alias: ProductAlias) -> None:
    await session.delete(alias)
    await session.commit()


async def get_many(
    session: AsyncSession, tenant_id: UUID, product_ids: list[UUID]
) -> dict[UUID, Product]:
    if not product_ids:
        return {}
    result = await session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id, Product.id.in_(product_ids)
        )
    )
    return {p.id: p for p in result.scalars().all()}


async def bulk_set_active(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    product_ids: list[UUID],
    active: bool,
) -> int:
    from sqlalchemy import update

    if not product_ids:
        return 0
    res = await session.execute(
        update(Product)
        .where(Product.tenant_id == tenant_id, Product.id.in_(product_ids))
        .values(active=active)
    )
    return res.rowcount or 0


async def list_categories(session: AsyncSession, tenant_id: UUID) -> list[str]:
    return await list_categories_by_tenants(session, [tenant_id])


async def list_categories_by_tenants(
    session: AsyncSession, tenant_ids: list[UUID],
) -> list[str]:
    if not tenant_ids:
        return []
    result = await session.execute(
        select(Product.category)
        .where(Product.tenant_id.in_(tenant_ids), Product.category.is_not(None))
        .distinct()
        .order_by(Product.category)
    )
    return [row[0] for row in result.all()]


async def list_by_category(
    session: AsyncSession, tenant_id: UUID, category: str
) -> list[Product]:
    result = await session.execute(
        select(Product).where(
            Product.tenant_id == tenant_id, Product.category == category
        )
    )
    return list(result.scalars().all())


async def merge_into(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    primary_id: UUID,
    duplicate_ids: list[UUID],
) -> dict[str, int]:
    """
    Mută raw_sales + product_aliases de la duplicate la primary, apoi
    șterge duplicate. Apelantul face commit.
    """
    from sqlalchemy import delete, update

    from app.modules.sales.models import RawSale

    dup_set = [d for d in duplicate_ids if d != primary_id]
    if not dup_set:
        return {
            "merged_count": 0,
            "aliases_reassigned": 0,
            "sales_reassigned": 0,
        }

    found = await get_many(session, tenant_id, [primary_id] + dup_set)
    if primary_id not in found:
        raise ValueError("primary_not_found")
    missing = [str(d) for d in dup_set if d not in found]
    if missing:
        raise ValueError(f"duplicates_not_found:{','.join(missing)}")

    sales_res = await session.execute(
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.product_id.in_(dup_set))
        .values(product_id=primary_id)
    )
    sales_reassigned = sales_res.rowcount or 0

    alias_res = await session.execute(
        update(ProductAlias)
        .where(
            ProductAlias.tenant_id == tenant_id,
            ProductAlias.product_id.in_(dup_set),
        )
        .values(product_id=primary_id)
    )
    aliases_reassigned = alias_res.rowcount or 0

    await session.execute(
        delete(Product).where(Product.tenant_id == tenant_id, Product.id.in_(dup_set))
    )

    return {
        "merged_count": len(dup_set),
        "aliases_reassigned": aliases_reassigned,
        "sales_reassigned": sales_reassigned,
    }
