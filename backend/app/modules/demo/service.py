"""Demo cleanup tools — pastram doar `wipe_tenant_data` pentru reset rapid.

Functia `seed_demo_data` (care popula sintetic stores/agents/products/sales)
a fost sterssa: nu mai cream agenti / store-uri sintetic. Datele de test sunt
gestionate prin import-uri reale sau direct prin admin UI.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


async def wipe_tenant_data(
    session: AsyncSession, *, tenant_id: UUID,
) -> dict[str, int]:
    """Sterge TOATE datele tenantului (vanzari, entitati canonice, aliases,
    batches, assignments). NU sterge userii, organizatia, audit log-urile sau
    api key-urile. Folosit ca reset rapid in conturile de test.
    """
    from app.modules.activitate.models import AgentVisit
    from app.modules.agents.models import Agent, AgentAlias, AgentStoreAssignment
    from app.modules.brands.models import Brand, BrandAlias
    from app.modules.parcurs.models import TravelSheet
    from app.modules.probleme.models import ActivityProblem
    from app.modules.product_categories.models import ProductCategoryAlias
    from app.modules.products.models import Product, ProductAlias
    from app.modules.sales.models import ImportBatch, RawSale
    from app.modules.stores.models import Store, StoreAlias

    counts: dict[str, int] = {}
    # ProductCategory e global — NU se sterge la wipe.
    # travel_sheet_entries + travel_sheet_fuel_fills se sterg cascade via FK.
    for model, key in [
        (AgentVisit, "visits"),
        (TravelSheet, "travel_sheets"),
        (ActivityProblem, "problems"),
        (RawSale, "sales"),
        (ImportBatch, "batches"),
        (AgentStoreAssignment, "assignments"),
        (StoreAlias, "store_aliases"),
        (AgentAlias, "agent_aliases"),
        (ProductAlias, "product_aliases"),
        (ProductCategoryAlias, "category_aliases"),
        (BrandAlias, "brand_aliases"),
        (Store, "stores"),
        (Agent, "agents"),
        (Product, "products"),
        (Brand, "brands"),
    ]:
        res = await session.execute(
            delete(model).where(model.tenant_id == tenant_id)
        )
        counts[key] = res.rowcount or 0

    await session.commit()
    return counts
