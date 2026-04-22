"""
Service pentru modulul `orders` (comenzi open — ADP + Sika).

Urmează contractul din `sales.service`: tenant-scoped, primește map-uri
raw→canonical_id ca parametri (store_id / agent_id / product_id).

Scope delete: `source + report_date`. Cumulative — re-upload cu același
(source, report_date) înlocuiește doar acel snapshot. Izolare per-sursă:
un upload ADP NU atinge rânduri Sika și invers.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orders.models import RawOrder
from app.modules.sales.models import ImportBatch


_BATCH_SOURCE_PREFIX = "orders_"  # batch.source = 'orders_adp' / 'orders_sika'


def batch_source_for(source: str) -> str:
    return f"{_BATCH_SOURCE_PREFIX}{source.lower()}"


async def create_batch(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    uploaded_by_user_id: UUID,
    filename: str,
    source: str,
) -> ImportBatch:
    batch = ImportBatch(
        tenant_id=tenant_id,
        uploaded_by_user_id=uploaded_by_user_id,
        filename=filename,
        source=batch_source_for(source),
    )
    session.add(batch)
    await session.flush()
    return batch


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


async def delete_by_report_date(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    source: str,
    report_date: date,
) -> int:
    """
    Șterge toate raw_orders din tenant pentru (source, report_date). Snapshot
    cumulative: re-upload aceeași zi = replace; celelalte zile intacte.
    """
    stmt = delete(RawOrder).where(
        RawOrder.tenant_id == tenant_id,
        RawOrder.source == source.lower(),
        RawOrder.report_date == report_date,
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def bulk_insert(
    session: AsyncSession,
    tenant_id: UUID,
    batch_id: UUID,
    rows: list[dict[str, Any]],
    *,
    report_date: date,
    year: int,
    month: int,
    client_to_store: dict[str, UUID] | None = None,
    code_to_product: dict[str, UUID] | None = None,
) -> int:
    if not rows:
        return 0
    store_map = client_to_store or {}
    product_map = code_to_product or {}
    for row in rows:
        row["tenant_id"] = tenant_id
        row["batch_id"] = batch_id
        row["report_date"] = report_date
        row["year"] = year
        row["month"] = month
        row["store_id"] = store_map.get(row["client"])
        raw_code = row.get("product_code")
        row["product_id"] = product_map.get(raw_code) if raw_code else None
        # agent_id se populează prin backfill ulterior din StoreAgentMapping
        # (ambele surse ADP+Sika folosesc Raf mapping, la fel ca raw_sales).
        row.setdefault("agent_id", None)

    await session.execute(RawOrder.__table__.insert(), rows)
    return len(rows)


async def list_batches(
    session: AsyncSession, tenant_id: UUID, *, source: str | None = None,
) -> list[ImportBatch]:
    filters = [ImportBatch.tenant_id == tenant_id]
    if source is not None:
        filters.append(ImportBatch.source == batch_source_for(source))
    else:
        filters.append(ImportBatch.source.like(f"{_BATCH_SOURCE_PREFIX}%"))
    stmt = select(ImportBatch).where(*filters).order_by(ImportBatch.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())
