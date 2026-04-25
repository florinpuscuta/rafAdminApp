"""Reguli discount — matrix get/upsert.

Matricea pentru scope='adp':
  - clientii KA cu vanzari `sales_xlsx`+'KA' in tenant (DEDEMAN, HORNBACH,
    LEROY, ALTEX) — extrasi din raw_sales pentru a evita hardcoding-ul.
  - grupele: toate ProductCategory (sortate dupa sort_order) + 'Marca Privata'
    ca rand singleton (group_kind='private_label').

Pentru scope='sika' — schelet pregatit (TM-uri ca grupe), implementare
ulterioara.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, distinct, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.brands.models import Brand
from app.modules.discount_rules.models import DiscountRule
from app.modules.product_categories.models import ProductCategory
from app.modules.products.models import Product
from app.modules.sales.models import ImportBatch, RawSale


SCOPES = ("adp", "sika")
PRIVATE_LABEL_KEY = "marca_privata"
PRIVATE_LABEL_LABEL = "Marca Privata"


async def list_clients(
    session: AsyncSession, tenant_id: UUID, scope: str,
) -> list[dict]:
    """Distinct client_canonical (chain) din vanzarile KA pentru scope-ul dat."""
    sources = ["sales_xlsx"] if scope == "adp" else ["sika_mtd_xlsx", "sika_xlsx"]
    chain_expr = func.split_part(RawSale.client, " | ", 1).label("chain")
    res = await session.execute(
        select(distinct(chain_expr))
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            RawSale.tenant_id == tenant_id,
            ImportBatch.source.in_(sources),
            func.upper(RawSale.channel) == "KA",
        )
        .order_by(chain_expr)
    )
    out = []
    for row in res:
        canonical = row[0] or ""
        if not canonical.strip():
            continue
        out.append({"canonical": canonical, "label": canonical})
    return out


async def list_groups(
    session: AsyncSession, tenant_id: UUID, scope: str,
) -> list[dict]:
    """
    Returneaza grupele relevante pentru scope:
      - ADP: categoriile cu produse brand non-private label care au vanzari
        KA in `sales_xlsx`. Marca Privata e rand separat (toate produsele
        is_private_label=true), nu e suprapusa cu o categorie.
      - SIKA: TM-urile (target markets) Sika.
    """
    if scope == "adp":
        # Categorii cu produse brand!=private_label si vanzari KA
        cat_stmt = (
            select(
                ProductCategory.code,
                ProductCategory.label,
                ProductCategory.sort_order,
            )
            .join(Product, Product.category_id == ProductCategory.id)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .join(RawSale, RawSale.product_id == Product.id)
            .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
            .where(
                Product.tenant_id == tenant_id,
                ImportBatch.source == "sales_xlsx",
                func.upper(RawSale.channel) == "KA",
                func.coalesce(Brand.is_private_label, False).is_(False),
            )
            .group_by(
                ProductCategory.code, ProductCategory.label,
                ProductCategory.sort_order,
            )
            .order_by(ProductCategory.sort_order, ProductCategory.code)
        )
        cats = (await session.execute(cat_stmt)).all()
        out = [
            {"kind": "category", "key": c.code, "label": c.label}
            for c in cats
        ]
        # Marca Privata — rand separat (singleton, toate produsele PL)
        pl_check = await session.execute(
            select(func.count())
            .select_from(Product)
            .outerjoin(Brand, Brand.id == Product.brand_id)
            .join(RawSale, RawSale.product_id == Product.id)
            .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
            .where(
                Product.tenant_id == tenant_id,
                ImportBatch.source == "sales_xlsx",
                func.upper(RawSale.channel) == "KA",
                Brand.is_private_label.is_(True),
            )
        )
        if (pl_check.scalar() or 0) > 0:
            out.append({
                "kind": "private_label",
                "key": PRIVATE_LABEL_KEY,
                "label": PRIVATE_LABEL_LABEL,
            })
        return out

    # scope == "sika" — TM-uri cu produse care au vanzari KA in sika sources
    from app.modules.grupe_produse.service import _classify_sika_tm
    name_stmt = (
        select(Product.name)
        .join(RawSale, RawSale.product_id == Product.id)
        .join(ImportBatch, ImportBatch.id == RawSale.batch_id)
        .where(
            Product.tenant_id == tenant_id,
            ImportBatch.source.in_(["sika_mtd_xlsx", "sika_xlsx"]),
            func.upper(RawSale.channel) == "KA",
        )
        .distinct()
    )
    seen: set[str] = set()
    for name in (await session.execute(name_stmt)).scalars():
        seen.add(_classify_sika_tm(name or ""))
    return [
        {"kind": "tm", "key": tm, "label": tm}
        for tm in sorted(seen)
    ]


async def get_matrix(
    session: AsyncSession, tenant_id: UUID, scope: str,
) -> dict:
    clients = await list_clients(session, tenant_id, scope)
    groups = await list_groups(session, tenant_id, scope)
    res = await session.execute(
        select(
            DiscountRule.client_canonical,
            DiscountRule.group_kind,
            DiscountRule.group_key,
            DiscountRule.applies,
        ).where(
            DiscountRule.tenant_id == tenant_id,
            DiscountRule.scope == scope,
        )
    )
    cells = [
        {
            "client_canonical": row.client_canonical,
            "group_kind": row.group_kind,
            "group_key": row.group_key,
            "applies": row.applies,
        }
        for row in res
    ]
    return {
        "scope": scope,
        "clients": clients,
        "groups": groups,
        "cells": cells,
    }


async def bulk_upsert(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope: str,
    rules: list[dict],
) -> tuple[int, int]:
    """Pentru orice (client, group) primit:
      - daca `applies=True` (= default-ul), STERGE eventualul rand existent
        (regula explicita inutila la default → economisim rows).
      - daca `applies=False`, upsert-eaza randul.

    Returneaza (upserted, deleted)."""
    if not rules:
        return 0, 0

    payload_to_upsert = [r for r in rules if not r["applies"]]
    pairs_to_delete = [
        (r["client_canonical"], r["group_kind"], r["group_key"])
        for r in rules if r["applies"]
    ]

    upserted = 0
    deleted = 0

    if payload_to_upsert:
        from datetime import datetime  # noqa: F401
        rows = [
            {
                "tenant_id": tenant_id,
                "scope": scope,
                "client_canonical": r["client_canonical"],
                "group_kind": r["group_kind"],
                "group_key": r["group_key"],
                "applies": False,
            }
            for r in payload_to_upsert
        ]
        stmt = pg_insert(DiscountRule).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_discount_rules_tenant_client_scope_group",
            set_={"applies": stmt.excluded.applies},
        )
        await session.execute(stmt)
        upserted = len(rows)

    for cc, kind, key in pairs_to_delete:
        del_res = await session.execute(
            delete(DiscountRule).where(
                DiscountRule.tenant_id == tenant_id,
                DiscountRule.scope == scope,
                DiscountRule.client_canonical == cc,
                DiscountRule.group_kind == kind,
                DiscountRule.group_key == key,
            )
        )
        deleted += del_res.rowcount or 0

    await session.commit()
    return upserted, deleted


def applies_default(
    *, tenant_rules: dict[tuple[str, str, str], bool],
    client_canonical: str, group_kind: str, group_key: str,
) -> bool:
    """Helper folosit din modulul margine la distributie discount.
    Default = True; FALSE doar cand exista regula explicita.
    """
    return tenant_rules.get(
        (client_canonical, group_kind, group_key), True,
    )


async def load_rules_dict(
    session: AsyncSession, tenant_id: UUID, scope: str,
) -> dict[tuple[str, str, str], bool]:
    res = await session.execute(
        select(
            DiscountRule.client_canonical,
            DiscountRule.group_kind,
            DiscountRule.group_key,
            DiscountRule.applies,
        ).where(
            DiscountRule.tenant_id == tenant_id,
            DiscountRule.scope == scope,
        )
    )
    return {
        (row.client_canonical, row.group_kind, row.group_key): row.applies
        for row in res
    }
