"""
Async orchestrator pentru import orders (ADP + Sika).

Creează propria session (SessionLocal), actualizează job-ul pe etape,
parsează fișierul cu importer-ul corespunzător sursei, apoi scope-uie
delete-ul pe (source, report_date) și inserează rândurile noi.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.modules.audit import service as audit_service
from app.modules.orders import importer_adp as importer_adp
from app.modules.orders import importer_sika as importer_sika
from app.modules.orders import jobs
from app.modules.orders import service as orders_service
from app.modules.products import service as products_service
from app.modules.stores import service as stores_service

logger = logging.getLogger("adeplast.orders.import")

_INSERT_CHUNK_SIZE = 5000


class _ImportAborted(Exception):
    def __init__(self, message: str, code: str = "error"):
        self.message = message
        self.code = code
        super().__init__(message)


async def run_import_job(
    *,
    job_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    content: bytes,
    filename: str,
    source: str,
    report_date: date,
) -> None:
    try:
        await jobs.set_status(job_id, "running")
        async with SessionLocal() as session:
            result = await _run(
                session,
                job_id=job_id,
                tenant_id=tenant_id,
                user_id=user_id,
                content=content,
                filename=filename,
                source=source,
                report_date=report_date,
            )
        await jobs.set_done(job_id, result)
    except _ImportAborted as e:
        await jobs.set_error(job_id, message=e.message, code=e.code)
    except Exception as e:  # pragma: no cover
        logger.exception("orders import failed", extra={"job_id": str(job_id)})
        await jobs.set_error(job_id, message=str(e) or "Eroare internă", code="error")


async def _run(
    session: AsyncSession,
    *,
    job_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    content: bytes,
    filename: str,
    source: str,
    report_date: date,
) -> dict[str, Any]:
    src = source.lower()

    # ── Stage 1: parse ─────────────────────────────────────────────────
    if src == "adp":
        rows, errors = importer_adp.parse_xlsx(content)
    else:
        rows, errors = importer_sika.parse_xlsx(content)
    await jobs.finish_stage(job_id, "parse_main")

    if not rows and errors:
        raise _ImportAborted(
            message=errors[0] if errors else "Eroare de parsare",
            code="parse_error",
        )

    # ── Stage 2: delete snapshot existent (aceeași source + report_date) ──
    deleted = await orders_service.delete_by_report_date(
        session, tenant_id, source=src, report_date=report_date,
    )
    await jobs.finish_stage(job_id, "delete_old")

    # ── Stage 3: insert chunked ────────────────────────────────────────
    batch = await orders_service.create_batch(
        session,
        tenant_id=tenant_id,
        uploaded_by_user_id=user_id,
        filename=filename,
        source=src,
    )

    unique_clients = list({r["client"] for r in rows})
    unique_codes = list({r["product_code"] for r in rows if r.get("product_code")})
    client_to_store = await stores_service.resolve_map(session, tenant_id, unique_clients)
    code_to_product = await products_service.resolve_map(session, tenant_id, unique_codes)

    inserted = await _chunked_insert(
        session,
        tenant_id=tenant_id,
        batch_id=batch.id,
        rows=rows,
        report_date=report_date,
        year=report_date.year,
        month=report_date.month,
        client_to_store=client_to_store,
        code_to_product=code_to_product,
        job_id=job_id,
    )

    # ── Stage 4: finalize + audit ──────────────────────────────────────
    await orders_service.finalize_batch(
        session, batch, inserted=inserted, skipped=len(errors),
    )
    unmapped_clients = sum(1 for r in rows if r["client"] not in client_to_store)
    unmapped_products = sum(
        1 for r in rows
        if r.get("product_code") and r["product_code"] not in code_to_product
    )

    await audit_service.log_event(
        session,
        event_type="orders.batch_imported",
        tenant_id=tenant_id,
        user_id=user_id,
        target_type="import_batch",
        target_id=batch.id,
        metadata={
            "filename": filename,
            "source": src,
            "report_date": report_date.isoformat(),
            "inserted": inserted,
            "skipped": len(errors),
            "deleted": deleted,
        },
    )
    await jobs.finish_stage(job_id, "finalize")

    return {
        "inserted": inserted,
        "skipped": len(errors),
        "deleted_before_insert": deleted,
        "source": src,
        "report_date": report_date.isoformat(),
        "unmapped_clients": unmapped_clients,
        "unmapped_products": unmapped_products,
        "errors": errors[:50],
    }


async def _chunked_insert(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    batch_id: UUID,
    rows: list[dict[str, Any]],
    report_date: date,
    year: int,
    month: int,
    client_to_store: dict[str, UUID],
    code_to_product: dict[str, UUID],
    job_id: UUID,
) -> int:
    if not rows:
        return 0

    from app.modules.orders.models import RawOrder

    total = len(rows)
    for row in rows:
        row["tenant_id"] = tenant_id
        row["batch_id"] = batch_id
        row["report_date"] = report_date
        row["year"] = year
        row["month"] = month
        row["store_id"] = client_to_store.get(row["client"])
        raw_code = row.get("product_code")
        row["product_id"] = code_to_product.get(raw_code) if raw_code else None
        row.setdefault("agent_id", None)

    inserted = 0
    for start in range(0, total, _INSERT_CHUNK_SIZE):
        chunk = rows[start : start + _INSERT_CHUNK_SIZE]
        await session.execute(RawOrder.__table__.insert(), chunk)
        inserted += len(chunk)
        await jobs.update_stage(job_id, "insert", inserted / total * 100)
    return inserted
