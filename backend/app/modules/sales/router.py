from uuid import UUID

from fastapi import Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import (
    get_current_org_ids,
    get_current_tenant_id,
    get_current_user,
)
from fastapi import Request

import asyncio

from app.modules.agents import service as agents_service
from app.modules.audit import service as audit_service
from app.modules.products import service as products_service
from app.modules.sales import backfill as sales_backfill
from app.modules.sales import import_service as sales_import_service
from app.modules.sales import importer as sales_importer
from app.modules.sales import jobs as sales_jobs
from app.modules.sales import service as sales_service
from app.modules.sales.import_service import _ImportAborted, _normalize_alocare
from app.modules.sales.schemas import (
    AlocareSummary,
    ImportBatchOut,
    ImportJobAccepted,
    ImportJobStatus,
    ImportResponse,
    JobStageOut,
    SaleOut,
    SalesListResponse,
)
from app.modules.stores import service as stores_service
from app.modules.users.models import User

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("", response_model=SalesListResponse)
async def list_sales(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500, alias="pageSize"),
    store_id: UUID | None = Query(None, alias="storeId"),
    agent_id: UUID | None = Query(None, alias="agentId"),
    product_id: UUID | None = Query(None, alias="productId"),
    year: int | None = Query(None),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    items, total = await sales_service.list_by_tenants(
        session, org_ids,
        page=page, page_size=page_size,
        store_id=store_id, agent_id=agent_id, product_id=product_id, year=year,
    )
    return SalesListResponse(
        items=[SaleOut.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/import", response_model=ImportResponse)
async def import_sales(
    request: Request,
    file: UploadFile,
    full_reload: bool = Query(
        False,
        alias="fullReload",
        description="Dacă true: șterge toate raw_sales existente înainte de insert. "
                    "Dacă false (default): smart-incremental — șterge doar perechile "
                    "(an, lună) prezente în fișier, re-inserează.",
    ),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se acceptă doar fișiere .xlsx"},
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fișier gol"},
        )

    rows, errors = sales_importer.parse_xlsx(content)

    # Parsing errors → 400, ca user-ul să știe exact ce să corecteze.
    if not rows and errors:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "parse_error",
                "message": errors[0] if errors else "Eroare de parsare",
                "errors": errors[:20],
            },
        )

    # Alocare: dacă fișierul conține sheet-ul de mapare (Client, Ship-to,
    # Agent), îl procesăm ÎNAINTE de raw_sales ca să avem canonical-urile
    # + alias-urile gata la momentul resolve_map. NU e obligatoriu — dacă
    # lipsește, rândurile vor rămâne "unmapped" și user-ul le fixează prin
    # UI-ul Unmapped.
    alocare_rows = sales_importer.parse_alocare_sheet(content)
    alocare_summary = AlocareSummary()
    if alocare_rows:
        try:
            result = await _normalize_alocare(
                session,
                tenant_id=tenant_id,
                user_id=current_user.id,
                alocare_rows=alocare_rows,
            )
        except _ImportAborted as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": e.code, "message": e.message},
            )
        alocare_summary = AlocareSummary(
            rows_processed=len(alocare_rows),
            **result,
        )

    # Smart incremental: înainte de insert, ștergem conflictele.
    pairs = sorted({(r["year"], r["month"]) for r in rows})
    if full_reload:
        deleted = await sales_service.delete_all_raw_sales(
            session, tenant_id
        )
    else:
        deleted = await sales_service.delete_by_year_month_pairs(
            session, tenant_id, pairs
        )

    batch = await sales_service.create_batch(
        session,
        tenant_id=tenant_id,
        uploaded_by_user_id=current_user.id,
        filename=filename,
    )

    unique_clients = list({r["client"] for r in rows})
    unique_agents = list({r["agent"] for r in rows if r.get("agent")})
    unique_codes = list({r["product_code"] for r in rows if r.get("product_code")})
    client_to_store = await stores_service.resolve_map(
        session, tenant_id, unique_clients
    )
    agent_to_canonical = await agents_service.resolve_map(
        session, tenant_id, unique_agents
    )
    code_to_product = await products_service.resolve_map(
        session, tenant_id, unique_codes
    )

    inserted = await sales_service.bulk_insert(
        session,
        tenant_id,
        batch.id,
        rows,
        client_to_store=client_to_store,
        agent_to_canonical=agent_to_canonical,
        code_to_product=code_to_product,
    )
    await sales_service.finalize_batch(session, batch, inserted=inserted, skipped=len(errors))

    # Metrici de nemapate pe baza rândurilor inserate.
    unmapped_clients = sum(1 for r in rows if r["client"] not in client_to_store)
    unmapped_agents = sum(
        1 for r in rows
        if r.get("agent") and r["agent"] not in agent_to_canonical
    )
    unmapped_products = sum(
        1 for r in rows
        if r.get("product_code") and r["product_code"] not in code_to_product
    )
    months_affected = [f"{y}-{m:02d}" for y, m in pairs]

    await audit_service.log_event(
        session,
        event_type="sales.batch_imported",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="import_batch",
        target_id=batch.id,
        metadata={
            "filename": filename,
            "inserted": inserted,
            "skipped": len(errors),
            "deleted": deleted,
            "full_reload": full_reload,
            "months_affected": months_affected,
        },
        request=request,
    )
    return ImportResponse(
        inserted=inserted,
        skipped=len(errors),
        deleted_before_insert=deleted,
        months_affected=months_affected,
        unmapped_clients=unmapped_clients,
        unmapped_agents=unmapped_agents,
        unmapped_products=unmapped_products,
        alocare=alocare_summary,
        errors=errors[:50],
    )


@router.post("/import/async", response_model=ImportJobAccepted, status_code=202)
async def import_sales_async(
    file: UploadFile,
    full_reload: bool = Query(False, alias="fullReload"),
    source: str = Query("adp", description="'adp', 'sika' sau 'sika_mtd' — alege parser-ul și izolează batch-urile pe source."),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Start un job de import în background și returnează imediat `job_id`.
    Clientul poll-uiește `/import/jobs/{job_id}` pentru progres pe etape.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se acceptă doar fișiere .xlsx"},
        )
    src_lower = (source or "adp").lower()
    if src_lower not in ("adp", "sika", "sika_mtd"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_source", "message": "source trebuie 'adp', 'sika' sau 'sika_mtd'"},
        )

    # Guard: source-ul trebuie sa corespunda org-ului activ.
    from app.modules.tenants.models import Organization
    org_slug = (await session.execute(
        select(Organization.slug).where(Organization.id == tenant_id)
    )).scalar_one_or_none()
    expected_slug = "adeplast" if src_lower == "adp" else "sika"
    if org_slug and org_slug != expected_slug:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "wrong_org",
                "message": (
                    f"Source '{src_lower}' nu poate fi încărcat în organizația '{org_slug}'. "
                    f"Comută pe organizația '{expected_slug}' și reîncarcă."
                ),
            },
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fișier gol"},
        )

    existing = sales_jobs.has_active_job(tenant_id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "import_in_progress",
                "message": "Un import e deja în curs pentru acest tenant.",
                "job_id": str(existing.id),
            },
        )

    job = await sales_jobs.create_job(tenant_id=tenant_id)
    asyncio.create_task(
        sales_import_service.run_import_job(
            job_id=job.id,
            tenant_id=tenant_id,
            user_id=current_user.id,
            content=content,
            filename=filename,
            full_reload=full_reload,
            source=src_lower,
        )
    )
    return ImportJobAccepted(job_id=job.id)


@router.get("/import/jobs/{job_id}", response_model=ImportJobStatus)
async def get_import_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
):
    job = sales_jobs.get_job(job_id)
    if job is None or job.tenant_id not in org_ids:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "job_not_found", "message": "Job inexistent"},
        )
    result_model: ImportResponse | None = None
    if job.result is not None:
        result_model = ImportResponse(**job.result)
    return ImportJobStatus(
        id=job.id,
        status=job.status,
        stages=[
            JobStageOut(key=s.key, label=s.label, progress=s.progress, done=s.done)
            for s in job.stages
        ],
        current_stage=job.current_stage,
        overall_progress=job.overall_progress,
        result=result_model,
        error=job.error,
        error_code=job.error_code,
    )


@router.post("/backfill")
async def backfill_fks(
    request: Request,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """
    Backfill `store_id` și `agent_id` pe raw_sales existente.
      - ADP: match pe nume combined (client_original | ship_to_original)
      - SIKA: match pe cod ship-to (primar) + nume (fallback)
    Rulează ambele surse la rând.
    """
    adp_result = await sales_backfill.run_full_backfill(
        session, tenant_id,
        resolved_by_user_id=current_user.id, source="ADP",
    )
    sika_result = await sales_backfill.run_full_backfill(
        session, tenant_id,
        resolved_by_user_id=current_user.id, source="SIKA",
    )
    result = {"adp": adp_result, "sika": sika_result}
    await audit_service.log_event(
        session,
        event_type="sales.backfill_fks",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="tenant",
        target_id=tenant_id,
        metadata={"result": str(result)[:500]},
        request=request,
    )
    return result


@router.get("/export")
async def export_sales(
    year: int | None = None,
    month: int | None = None,
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    """Returnează un .xlsx cu toate raw_sales filtrate (year/month opțional)."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook

    rows = await sales_service.list_all_by_tenants(
        session, org_ids, year=year, month=month
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "sales"
    headers = [
        "year", "month", "client", "channel", "product_code", "product_name",
        "category_code", "amount", "quantity", "agent",
        "store_id", "agent_id", "product_id", "created_at",
    ]
    ws.append(headers)
    for r in rows:
        ws.append([
            r.year, r.month, r.client, r.channel, r.product_code, r.product_name,
            r.category_code,
            float(r.amount) if r.amount is not None else None,
            float(r.quantity) if r.quantity is not None else None,
            r.agent,
            str(r.store_id) if r.store_id else None,
            str(r.agent_id) if r.agent_id else None,
            str(r.product_id) if r.product_id else None,
            r.created_at.isoformat() if r.created_at else None,
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname_parts = ["sales"]
    if year: fname_parts.append(str(year))
    if month: fname_parts.append(f"m{month:02d}")
    filename = "_".join(fname_parts) + ".xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/batches", response_model=list[ImportBatchOut])
async def list_batches(
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    batches = await sales_service.list_batches_by_tenants(session, org_ids)
    return [ImportBatchOut.model_validate(b) for b in batches]


@router.delete("/batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_batch(
    request: Request,
    batch_id: UUID,
    current_user: User = Depends(get_current_user),
    org_ids: list[UUID] = Depends(get_current_org_ids),
    session: AsyncSession = Depends(get_session),
):
    deleted = None
    owner_tenant = None
    for tid in org_ids:
        deleted = await sales_service.delete_batch(session, tid, batch_id)
        if deleted is not None:
            owner_tenant = tid
            break
    if deleted is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "batch_not_found", "message": "Batch inexistent"},
        )
    await audit_service.log_event(
        session,
        event_type="sales.batch_deleted",
        tenant_id=owner_tenant,
        user_id=current_user.id,
        target_type="import_batch",
        target_id=batch_id,
        metadata={"filename": deleted.filename, "inserted_rows": deleted.inserted_rows},
        request=request,
    )
    return None
