"""
Public service pentru modulul `sales`. Toate query-urile sunt tenant-scoped.

Enrichment note: acest modul NU cunoaște `stores`, `agents`, etc. Expune
funcții care acceptă map-uri raw→canonical_id ca parametru (contract pur de
date) — modulele canonice apelează aceste funcții după ce-și creează alias-urile.
"""
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sales.models import ImportBatch, RawSale


# Canalul analizat: DOAR KA (traditional trade / RETAIL e exclus prin design —
# nu ne interesează în nicio agregare). Aplicat sistematic la:
# overview_totals, sum_by_store, sum_by_month, sum_by_agent, sum_by_product,
# available_years și list_by_tenant. Raw data e păstrată intactă în DB.
ANALYTICS_CHANNEL = "KA"


def _ka_filter():
    return func.upper(RawSale.channel) == ANALYTICS_CHANNEL


async def list_all_by_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    year: int | None = None,
    month: int | None = None,
) -> list[RawSale]:
    """Fără paginare — pentru export Excel."""
    filters = [RawSale.tenant_id == tenant_id]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    stmt = (
        select(RawSale)
        .where(*filters)
        .order_by(RawSale.year.desc(), RawSale.month.desc(), RawSale.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_by_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    page: int = 1,
    page_size: int = 50,
    store_id: UUID | None = None,
    agent_id: UUID | None = None,
    product_id: UUID | None = None,
    year: int | None = None,
) -> tuple[list[RawSale], int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 500))

    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if store_id is not None:
        filters.append(RawSale.store_id == store_id)
    if agent_id is not None:
        filters.append(RawSale.agent_id == agent_id)
    if product_id is not None:
        filters.append(RawSale.product_id == product_id)
    if year is not None:
        filters.append(RawSale.year == year)

    total_stmt = select(func.count(RawSale.id)).where(*filters)
    total = (await session.execute(total_stmt)).scalar_one()

    stmt = (
        select(RawSale)
        .where(*filters)
        .order_by(RawSale.year.desc(), RawSale.month.desc(), RawSale.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total


async def create_batch(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    uploaded_by_user_id: UUID,
    filename: str,
    source: str = "sales_xlsx",
) -> ImportBatch:
    batch = ImportBatch(
        tenant_id=tenant_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        source=source,
    )
    session.add(batch)
    await session.flush()
    return batch


async def bulk_insert(
    session: AsyncSession,
    tenant_id: UUID,
    batch_id: UUID,
    rows: list[dict[str, Any]],
    *,
    client_to_store: dict[str, UUID] | None = None,
    agent_to_canonical: dict[str, UUID] | None = None,
    code_to_product: dict[str, UUID] | None = None,
) -> int:
    if not rows:
        return 0
    store_map = client_to_store or {}
    agent_map = agent_to_canonical or {}
    product_map = code_to_product or {}
    for row in rows:
        row["tenant_id"] = tenant_id
        row["batch_id"] = batch_id
        row["store_id"] = store_map.get(row["client"])
        raw_agent = row.get("agent")
        row["agent_id"] = agent_map.get(raw_agent) if raw_agent else None
        raw_code = row.get("product_code")
        row["product_id"] = product_map.get(raw_code) if raw_code else None

    await session.execute(RawSale.__table__.insert(), rows)
    return len(rows)


async def finalize_batch(
    session: AsyncSession,
    batch: ImportBatch,
    *,
    inserted: int,
    skipped: int,
) -> None:
    batch.inserted_rows = inserted
    batch.skipped_rows = skipped
    await session.commit()


async def delete_by_year_month_pairs(
    session: AsyncSession,
    tenant_id: UUID,
    pairs: list[tuple[int, int]],
    *,
    batch_source: str | None = None,
) -> int:
    """
    Șterge toate raw_sales din tenant pentru perechile (year, month) date.
    Folosit pentru smart-incremental la upload: înainte să inserezi batch-ul
    nou, ștergi rândurile vechi din aceleași luni ca să nu ai duplicate.

    Dacă `batch_source` e setat (ex. 'sika_xlsx'), șterge DOAR rândurile din
    batch-uri cu acel source — izolează ADP de SIKA.
    Returnează numărul de rânduri șterse.
    """
    from sqlalchemy import and_, delete, or_, tuple_

    if not pairs:
        return 0

    if batch_source is not None:
        # Scoped delete prin join explicit pe import_batches.source.
        placeholders = []
        params: dict[str, Any] = {"tid": str(tenant_id), "bsrc": batch_source}
        for i, (y, m) in enumerate(pairs):
            placeholders.append(f"(:y{i}, :m{i})")
            params[f"y{i}"] = y
            params[f"m{i}"] = m
        pairs_sql = ", ".join(placeholders)
        from sqlalchemy import text
        stmt = text(f"""
            DELETE FROM raw_sales rs
            USING import_batches b
            WHERE b.id = rs.batch_id
              AND b.source = :bsrc
              AND rs.tenant_id = :tid
              AND (rs.year, rs.month) IN ({pairs_sql})
        """)
        result = await session.execute(stmt, params)
        return result.rowcount or 0

    stmt = delete(RawSale).where(
        RawSale.tenant_id == tenant_id,
        tuple_(RawSale.year, RawSale.month).in_(pairs),
    )
    try:
        result = await session.execute(stmt)
    except Exception:
        conds = [and_(RawSale.year == y, RawSale.month == m) for y, m in pairs]
        stmt = delete(RawSale).where(RawSale.tenant_id == tenant_id, or_(*conds))
        result = await session.execute(stmt)
    return result.rowcount or 0


async def delete_all_raw_sales(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    batch_source: str | None = None,
) -> int:
    """
    Ștergere TOTALĂ (full_reload) — păstrează canonical entities + aliases.
    Dacă `batch_source` e setat, șterge DOAR rândurile din batch-uri cu acel
    source — izolează ADP de SIKA.
    """
    from sqlalchemy import delete, text

    if batch_source is not None:
        stmt = text("""
            DELETE FROM raw_sales rs
            USING import_batches b
            WHERE b.id = rs.batch_id
              AND b.source = :bsrc
              AND rs.tenant_id = :tid
        """)
        result = await session.execute(
            stmt, {"tid": str(tenant_id), "bsrc": batch_source}
        )
        return result.rowcount or 0

    stmt = delete(RawSale).where(RawSale.tenant_id == tenant_id)
    result = await session.execute(stmt)
    return result.rowcount or 0


async def list_batches(session: AsyncSession, tenant_id: UUID) -> list[ImportBatch]:
    stmt = (
        select(ImportBatch)
        .where(ImportBatch.tenant_id == tenant_id)
        .order_by(ImportBatch.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_batch(
    session: AsyncSession, tenant_id: UUID, batch_id: UUID
) -> ImportBatch | None:
    """
    Șterge batch-ul + TOATE raw_sales asociate (via ON DELETE CASCADE pe FK).
    Returnează batch-ul șters (pentru confirmare) sau None dacă nu există.
    """
    batch = await session.get(ImportBatch, batch_id)
    if batch is None or batch.tenant_id != tenant_id:
        return None
    await session.delete(batch)
    await session.commit()
    return batch


async def list_clients_without_store(
    session: AsyncSession, tenant_id: UUID
) -> list[tuple[str, int, Decimal]]:
    """
    Returnează [(raw_client, row_count, total_amount), ...] pentru rândurile
    care încă nu au fost legate de un Store canonic. Folosit de UI "Unmapped".
    """
    stmt = (
        select(
            RawSale.client,
            func.count(RawSale.id).label("row_count"),
            func.coalesce(func.sum(RawSale.amount), 0).label("total_amount"),
        )
        .where(RawSale.tenant_id == tenant_id, RawSale.store_id.is_(None))
        .group_by(RawSale.client)
        .order_by(func.count(RawSale.id).desc())
    )
    result = await session.execute(stmt)
    return [(row[0], int(row[1]), Decimal(row[2])) for row in result.all()]


async def backfill_store_for_client(
    session: AsyncSession, tenant_id: UUID, raw_client: str, store_id: UUID
) -> int:
    """
    Setează store_id pe toate raw_sales unde client=raw_client și store_id IS NULL.
    Returnează numărul de rânduri afectate.
    """
    stmt = (
        update(RawSale)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.client == raw_client,
            RawSale.store_id.is_(None),
        )
        .values(store_id=store_id)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def list_agents_without_canonical(
    session: AsyncSession, tenant_id: UUID
) -> list[tuple[str, int, Decimal]]:
    """
    [(raw_agent, row_count, total_amount), ...] pentru rândurile cu `agent`
    NOT NULL dar fără agent canonic asociat. Folosit de UI "Unmapped agenți".
    """
    stmt = (
        select(
            RawSale.agent,
            func.count(RawSale.id).label("row_count"),
            func.coalesce(func.sum(RawSale.amount), 0).label("total_amount"),
        )
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.agent.is_not(None),
            RawSale.agent_id.is_(None),
        )
        .group_by(RawSale.agent)
        .order_by(func.count(RawSale.id).desc())
    )
    result = await session.execute(stmt)
    return [(row[0], int(row[1]), Decimal(row[2])) for row in result.all()]


async def backfill_agent_for_raw(
    session: AsyncSession, tenant_id: UUID, raw_agent: str, agent_id: UUID
) -> int:
    stmt = (
        update(RawSale)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.agent == raw_agent,
            RawSale.agent_id.is_(None),
        )
        .values(agent_id=agent_id)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def clear_store_for_client(
    session: AsyncSession, tenant_id: UUID, raw_client: str
) -> int:
    """Șterge legătura store_id pentru raw_sales cu client=raw_client."""
    stmt = (
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.client == raw_client)
        .values(store_id=None)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def clear_agent_for_raw(
    session: AsyncSession, tenant_id: UUID, raw_agent: str
) -> int:
    stmt = (
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.agent == raw_agent)
        .values(agent_id=None)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def clear_product_for_raw(
    session: AsyncSession, tenant_id: UUID, raw_code: str
) -> int:
    stmt = (
        update(RawSale)
        .where(RawSale.tenant_id == tenant_id, RawSale.product_code == raw_code)
        .values(product_id=None)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def list_products_without_canonical(
    session: AsyncSession, tenant_id: UUID
) -> list[tuple[str, str | None, int, Decimal]]:
    """
    [(raw_code, sample_name, row_count, total_amount), ...] pentru rândurile
    cu product_code NOT NULL și product_id NULL. `sample_name` e un
    product_name găsit pentru orientare vizuală.
    """
    stmt = (
        select(
            RawSale.product_code,
            func.min(RawSale.product_name),
            func.count(RawSale.id),
            func.coalesce(func.sum(RawSale.amount), 0),
        )
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.product_code.is_not(None),
            RawSale.product_id.is_(None),
        )
        .group_by(RawSale.product_code)
        .order_by(func.count(RawSale.id).desc())
    )
    result = await session.execute(stmt)
    return [(r[0], r[1], int(r[2]), Decimal(r[3])) for r in result.all()]


async def backfill_product_for_raw(
    session: AsyncSession, tenant_id: UUID, raw_code: str, product_id: UUID
) -> int:
    stmt = (
        update(RawSale)
        .where(
            RawSale.tenant_id == tenant_id,
            RawSale.product_code == raw_code,
            RawSale.product_id.is_(None),
        )
        .values(product_id=product_id)
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


# ── Aggregations pentru dashboard ─────────────────────────────────────────
# sales.service deține toate agregările pe raw_sales (tabela proprie).
# Returnează ID-uri brute (store_id, agent_id) — router-ul apelant hidratează
# cu nume prin stores/agents.service.get_many.

async def available_years(session: AsyncSession, tenant_id: UUID) -> list[int]:
    stmt = (
        select(RawSale.year)
        .where(RawSale.tenant_id == tenant_id, _ka_filter())
        .group_by(RawSale.year)
        .order_by(RawSale.year.desc())
    )
    result = await session.execute(stmt)
    return [int(r[0]) for r in result.all()]


async def overview_totals(
    session: AsyncSession,
    tenant_id: UUID,
    year: int | None = None,
    month: int | None = None,
    store_id: UUID | None = None,
    agent_id: UUID | None = None,
    product_id: UUID | None = None,
    store_ids_in: list[UUID] | None = None,
    product_ids_in: list[UUID] | None = None,
) -> dict[str, Any]:
    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    if store_id is not None:
        filters.append(RawSale.store_id == store_id)
    if agent_id is not None:
        filters.append(RawSale.agent_id == agent_id)
    if product_id is not None:
        filters.append(RawSale.product_id == product_id)
    if store_ids_in is not None:
        # listă goală → 0 rezultate (nu ignorăm filtrul)
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    if product_ids_in is not None:
        filters.append(RawSale.product_id.in_(product_ids_in) if product_ids_in else RawSale.id == None)

    stmt = select(
        func.count(RawSale.id),
        func.coalesce(func.sum(RawSale.amount), 0),
        func.count(func.distinct(RawSale.store_id)),
        func.count(func.distinct(RawSale.agent_id)),
    ).where(*filters)
    row = (await session.execute(stmt)).one()

    unmapped_stmt = select(func.count(RawSale.id)).where(
        *filters, RawSale.store_id.is_(None)
    )
    unmapped_stores = (await session.execute(unmapped_stmt)).scalar_one()

    unmapped_agent_stmt = select(func.count(RawSale.id)).where(
        *filters, RawSale.agent.is_not(None), RawSale.agent_id.is_(None)
    )
    unmapped_agents = (await session.execute(unmapped_agent_stmt)).scalar_one()

    return {
        "total_rows": int(row[0]),
        "total_amount": Decimal(row[1]),
        "distinct_mapped_stores": int(row[2]),
        "distinct_mapped_agents": int(row[3]),
        "unmapped_store_rows": int(unmapped_stores),
        "unmapped_agent_rows": int(unmapped_agents),
    }


async def sum_by_store(
    session: AsyncSession,
    tenant_id: UUID,
    year: int | None,
    limit: int | None = 10,
    month: int | None = None,
    agent_id: UUID | None = None,
    product_id: UUID | None = None,
    store_ids_in: list[UUID] | None = None,
    product_ids_in: list[UUID] | None = None,
) -> list[tuple[UUID | None, Decimal, int]]:
    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    if agent_id is not None:
        filters.append(RawSale.agent_id == agent_id)
    if product_id is not None:
        filters.append(RawSale.product_id == product_id)
    if store_ids_in is not None:
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    if product_ids_in is not None:
        filters.append(RawSale.product_id.in_(product_ids_in) if product_ids_in else RawSale.id == None)

    stmt = (
        select(
            RawSale.store_id,
            func.coalesce(func.sum(RawSale.amount), 0),
            func.count(RawSale.id),
        )
        .where(*filters)
        .group_by(RawSale.store_id)
        .order_by(func.sum(RawSale.amount).desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return [(row[0], Decimal(row[1]), int(row[2])) for row in result.all()]


async def stats_by_store(
    session: AsyncSession,
    tenant_id: UUID,
    year: int | None,
    *,
    month: int | None = None,
    store_ids_in: list[UUID] | None = None,
) -> list[tuple[UUID | None, Decimal, int, int]]:
    """[(store_id, total_amount, row_count, distinct_products), ...] ordonat după total_amount desc."""
    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    if store_ids_in is not None:
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    stmt = (
        select(
            RawSale.store_id,
            func.coalesce(func.sum(RawSale.amount), 0),
            func.count(RawSale.id),
            func.count(func.distinct(RawSale.product_id)),
        )
        .where(*filters)
        .group_by(RawSale.store_id)
        .order_by(func.sum(RawSale.amount).desc())
    )
    result = await session.execute(stmt)
    return [(r[0], Decimal(r[1]), int(r[2]), int(r[3])) for r in result.all()]


async def sum_by_month(
    session: AsyncSession,
    tenant_id: UUID,
    year: int,
    store_id: UUID | None = None,
    agent_id: UUID | None = None,
    product_id: UUID | None = None,
    store_ids_in: list[UUID] | None = None,
    product_ids_in: list[UUID] | None = None,
) -> list[tuple[int, Decimal, int]]:
    """[(month, total_amount, row_count), ...] pentru toate cele 12 luni ale anului."""
    filters = [RawSale.tenant_id == tenant_id, RawSale.year == year, _ka_filter()]
    if store_id is not None:
        filters.append(RawSale.store_id == store_id)
    if agent_id is not None:
        filters.append(RawSale.agent_id == agent_id)
    if product_id is not None:
        filters.append(RawSale.product_id == product_id)
    if store_ids_in is not None:
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    if product_ids_in is not None:
        filters.append(RawSale.product_id.in_(product_ids_in) if product_ids_in else RawSale.id == None)
    stmt = (
        select(
            RawSale.month,
            func.coalesce(func.sum(RawSale.amount), 0),
            func.count(RawSale.id),
        )
        .where(*filters)
        .group_by(RawSale.month)
    )
    result = await session.execute(stmt)
    partial = {int(r[0]): (Decimal(r[1]), int(r[2])) for r in result.all()}
    return [
        (m, partial.get(m, (Decimal(0), 0))[0], partial.get(m, (Decimal(0), 0))[1])
        for m in range(1, 13)
    ]


async def sum_by_agent(
    session: AsyncSession,
    tenant_id: UUID,
    year: int | None,
    limit: int = 10,
    month: int | None = None,
    store_id: UUID | None = None,
    product_id: UUID | None = None,
    store_ids_in: list[UUID] | None = None,
    product_ids_in: list[UUID] | None = None,
) -> list[tuple[UUID | None, Decimal, int]]:
    """Sumă per agent cu rezoluție canonică SAM (la fel ca Vz la zi / Analiza pe luni).

    Rândurile cu `agent_id IS NULL` sunt rezolvate la runtime prin SAM pe
    cheia `client_original | ship_to_original` (sau `cheie_finala`) și,
    ca fallback, prin `agent_store_assignments` pe `store_id`. Doar ce
    rămâne nerezolvat ajunge cu `agent_id=None` (bucket "Nemapați").
    """
    from app.modules.mappings.resolution import (
        client_sam_map,
        resolve as resolve_canonical,
        store_agent_map,
    )

    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    if store_id is not None:
        filters.append(RawSale.store_id == store_id)
    if product_id is not None:
        filters.append(RawSale.product_id == product_id)
    if store_ids_in is not None:
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    if product_ids_in is not None:
        filters.append(RawSale.product_id.in_(product_ids_in) if product_ids_in else RawSale.id == None)

    # Agregăm la nivel de (agent_id, store_id, client) ca să putem aplica SAM
    # per grup înainte de totalizarea pe agent.
    stmt = (
        select(
            RawSale.agent_id,
            RawSale.store_id,
            RawSale.client,
            func.coalesce(func.sum(RawSale.amount), 0).label("total"),
            func.count(RawSale.id).label("cnt"),
        )
        .where(*filters)
        .group_by(RawSale.agent_id, RawSale.store_id, RawSale.client)
    )
    rows = (await session.execute(stmt)).all()

    cmap = await client_sam_map(session, tenant_id)
    store_ids_to_resolve = {
        r.store_id for r in rows
        if r.agent_id is None and r.store_id is not None
    }
    smap = await store_agent_map(session, tenant_id, store_ids_to_resolve)

    agg: dict[UUID | None, list] = {}
    for r in rows:
        resolved_agent, _ = resolve_canonical(
            agent_id=r.agent_id,
            store_id=r.store_id,
            client=r.client,
            client_map=cmap,
            store_map=smap,
        )
        entry = agg.setdefault(resolved_agent, [Decimal(0), 0])
        entry[0] += Decimal(r.total)
        entry[1] += int(r.cnt)

    sorted_rows = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)
    return [(aid, total, cnt) for aid, (total, cnt) in sorted_rows[:limit]]


async def sum_by_product(
    session: AsyncSession,
    tenant_id: UUID,
    year: int | None,
    limit: int = 10,
    month: int | None = None,
    store_id: UUID | None = None,
    agent_id: UUID | None = None,
    store_ids_in: list[UUID] | None = None,
    product_ids_in: list[UUID] | None = None,
) -> list[tuple[UUID | None, Decimal, int, Decimal]]:
    """[(product_id, total_amount, row_count, total_quantity), ...] sortat desc."""
    filters = [RawSale.tenant_id == tenant_id, _ka_filter()]
    if year is not None:
        filters.append(RawSale.year == year)
    if month is not None:
        filters.append(RawSale.month == month)
    if store_id is not None:
        filters.append(RawSale.store_id == store_id)
    if agent_id is not None:
        filters.append(RawSale.agent_id == agent_id)
    if store_ids_in is not None:
        filters.append(RawSale.store_id.in_(store_ids_in) if store_ids_in else RawSale.id == None)
    if product_ids_in is not None:
        filters.append(RawSale.product_id.in_(product_ids_in) if product_ids_in else RawSale.id == None)

    stmt = (
        select(
            RawSale.product_id,
            func.coalesce(func.sum(RawSale.amount), 0),
            func.count(RawSale.id),
            func.coalesce(func.sum(RawSale.quantity), 0),
        )
        .where(*filters)
        .group_by(RawSale.product_id)
        .order_by(func.sum(RawSale.amount).desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return [
        (row[0], Decimal(row[1]), int(row[2]), Decimal(row[3])) for row in result.all()
    ]
