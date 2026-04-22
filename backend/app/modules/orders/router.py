"""
Router modul `orders` — upload async de snapshot-uri de comenzi open (ADP + Sika).

Endpoints:
  POST /api/orders/import/async?source=adp|sika&reportDate=YYYY-MM-DD
    → 202 { jobId }
  GET /api/orders/import/jobs/{job_id}
    → status + stages + result
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Query, UploadFile, status

from app.core.api import APIRouter
from app.modules.auth.deps import get_current_user
from app.modules.orders import import_service as orders_import_service
from app.modules.orders import jobs as orders_jobs
from app.modules.orders.schemas import (
    OrdersImportJobAccepted,
    OrdersImportJobStatus,
    OrdersImportResponse,
    OrdersJobStageOut,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/import/async", response_model=OrdersImportJobAccepted, status_code=202)
async def import_orders_async(
    file: UploadFile,
    source: str = Query(..., description="'adp' sau 'sika'"),
    report_date: str | None = Query(
        None, alias="reportDate",
        description="Data snapshot-ului (YYYY-MM-DD). Default: azi.",
    ),
    current_user: User = Depends(get_current_user),
):
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se acceptă doar fișiere .xlsx"},
        )
    src = (source or "").lower()
    if src not in ("adp", "sika"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_source", "message": "source trebuie 'adp' sau 'sika'"},
        )

    if report_date:
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "invalid_date",
                    "message": "reportDate trebuie format YYYY-MM-DD",
                },
            )
    else:
        rd = date.today()

    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fișier gol"},
        )

    existing = orders_jobs.has_active_job(current_user.tenant_id)
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "import_in_progress",
                "message": "Un import de comenzi e deja în curs pentru acest tenant.",
                "job_id": str(existing.id),
            },
        )

    job = await orders_jobs.create_job(tenant_id=current_user.tenant_id)
    asyncio.create_task(
        orders_import_service.run_import_job(
            job_id=job.id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            content=content,
            filename=filename,
            source=src,
            report_date=rd,
        )
    )
    return OrdersImportJobAccepted(job_id=job.id)


@router.get("/import/jobs/{job_id}", response_model=OrdersImportJobStatus)
async def get_orders_import_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    job = orders_jobs.get_job(job_id)
    if job is None or job.tenant_id != current_user.tenant_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "job_not_found", "message": "Job inexistent"},
        )
    result_model: OrdersImportResponse | None = None
    if job.result is not None:
        result_model = OrdersImportResponse(**job.result)
    return OrdersImportJobStatus(
        id=job.id,
        status=job.status,
        stages=[
            OrdersJobStageOut(key=s.key, label=s.label, progress=s.progress, done=s.done)
            for s in job.stages
        ],
        current_stage=job.current_stage,
        overall_progress=job.overall_progress,
        result=result_model,
        error=job.error,
        error_code=job.error_code,
    )
