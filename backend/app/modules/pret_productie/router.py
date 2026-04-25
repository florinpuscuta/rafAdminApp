from uuid import UUID

from fastapi import Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.audit import service as audit_service
from app.modules.auth.deps import get_current_tenant_id, get_current_user
from app.modules.pret_productie import service as svc
from app.modules.tenants.models import Organization
from app.modules.pret_productie.schemas import (
    PPListResponse,
    PPMonthlyListResponse,
    PPMonthlySlot,
    PPMonthlySummaryResponse,
    PPMonthlyUploadResponse,
    PPRow,
    PPScope,
    PPSummaryResponse,
    PPUploadResponse,
)
from app.modules.users.models import User


router = APIRouter(prefix="/api/pret-productie", tags=["pret-productie"])


def _validate_scope(scope: str) -> str:
    s = (scope or "").lower()
    if s not in svc.SCOPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_scope",
                "message": "scope trebuie 'adp' sau 'sika'",
            },
        )
    return s


async def _guard_scope_matches_org(
    session: AsyncSession, tenant_id: UUID, scope: str,
) -> None:
    org_slug = (await session.execute(
        select(Organization.slug).where(Organization.id == tenant_id)
    )).scalar_one_or_none()
    expected_slug = "adeplast" if scope == "adp" else "sika"
    if org_slug and org_slug != expected_slug:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "wrong_org",
                "message": (
                    f"Scope '{scope}' nu poate fi încărcat în organizația '{org_slug}'. "
                    f"Comută pe organizația '{expected_slug}' și reîncarcă."
                ),
            },
        )


@router.get("/summary", response_model=PPSummaryResponse)
async def summary(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPSummaryResponse:
    s = await svc.get_summary(session, tenant_id)
    return PPSummaryResponse(
        adp=PPScope(scope="adp", **s["adp"]),
        sika=PPScope(scope="sika", **s["sika"]),
    )


@router.get("", response_model=PPListResponse)
async def list_prices(
    scope: str = Query("adp"),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPListResponse:
    s = _validate_scope(scope)
    items = await svc.list_prices(session, tenant_id, s)
    return PPListResponse(
        scope=s,
        items=[PPRow(**it) for it in items],
    )


@router.post("/upload", response_model=PPUploadResponse)
async def upload(
    file: UploadFile,
    scope: str = Query("adp"),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPUploadResponse:
    s = _validate_scope(scope)
    await _guard_scope_matches_org(session, tenant_id, s)
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se accepta doar .xlsx"},
        )
    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fisier gol"},
        )

    try:
        parsed = svc.parse_xlsx(content)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "parse_error", "message": str(exc)},
        )

    inserted, deleted_before, unmatched = await svc.upsert_prices(
        session,
        tenant_id=tenant_id,
        scope=s,
        parsed_rows=parsed.rows,
        filename=filename,
    )

    await audit_service.log_event(
        session,
        event_type="pret_productie.uploaded",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="pret_productie",
        target_id=tenant_id,
        metadata={
            "scope": s,
            "filename": filename,
            "rows_total": len(parsed.rows) + parsed.invalid,
            "rows_matched": inserted,
            "rows_unmatched": len(unmatched),
            "rows_invalid": parsed.invalid,
            "deleted_before": deleted_before,
        },
    )

    return PPUploadResponse(
        scope=s,
        filename=filename,
        rows_total=len(parsed.rows) + parsed.invalid,
        rows_matched=inserted,
        rows_unmatched=len(unmatched),
        rows_invalid=parsed.invalid,
        unmatched_codes=unmatched[:50],
        inserted=inserted,
        deleted_before=deleted_before,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def reset(
    scope: str = Query("adp"),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    s = _validate_scope(scope)
    deleted = await svc.reset_scope(session, tenant_id, s)
    await audit_service.log_event(
        session,
        event_type="pret_productie.reset",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="pret_productie",
        target_id=tenant_id,
        metadata={"scope": s, "deleted": deleted},
    )
    return None


# ─── Snapshot lunar ──────────────────────────────────────────────────


def _validate_year_month(year: int, month: int) -> None:
    if not (2000 <= year <= 2100):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_year", "message": "an invalid"},
        )
    if not (1 <= month <= 12):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_month", "message": "luna trebuie 1..12"},
        )


@router.get("/monthly-summary", response_model=PPMonthlySummaryResponse)
async def monthly_summary(
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPMonthlySummaryResponse:
    s = await svc.get_monthly_summary(session, tenant_id)
    return PPMonthlySummaryResponse(
        adp=[PPMonthlySlot(**slot) for slot in s.get("adp", [])],
        sika=[PPMonthlySlot(**slot) for slot in s.get("sika", [])],
    )


@router.get("/monthly", response_model=PPMonthlyListResponse)
async def list_prices_monthly(
    scope: str = Query("adp"),
    year: int = Query(...),
    month: int = Query(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPMonthlyListResponse:
    s = _validate_scope(scope)
    _validate_year_month(year, month)
    items = await svc.list_prices_monthly(session, tenant_id, s, year, month)
    return PPMonthlyListResponse(
        scope=s, year=year, month=month,
        items=[PPRow(**it) for it in items],
    )


@router.post("/upload-monthly", response_model=PPMonthlyUploadResponse)
async def upload_monthly(
    file: UploadFile,
    scope: str = Query("adp"),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> PPMonthlyUploadResponse:
    s = _validate_scope(scope)
    _validate_year_month(year, month)
    await _guard_scope_matches_org(session, tenant_id, s)
    filename = file.filename or ""
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": "Se accepta doar .xlsx"},
        )
    content = await file.read()
    if not content:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Fisier gol"},
        )
    try:
        parsed = svc.parse_xlsx(content)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "parse_error", "message": str(exc)},
        )

    inserted, deleted_before, unmatched = await svc.upsert_prices_monthly(
        session,
        tenant_id=tenant_id,
        scope=s, year=year, month=month,
        parsed_rows=parsed.rows,
        filename=filename,
    )

    await audit_service.log_event(
        session,
        event_type="pret_productie.monthly_uploaded",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="pret_productie_monthly",
        target_id=tenant_id,
        metadata={
            "scope": s, "year": year, "month": month,
            "filename": filename,
            "rows_total": len(parsed.rows) + parsed.invalid,
            "rows_matched": inserted,
            "rows_unmatched": len(unmatched),
            "rows_invalid": parsed.invalid,
            "deleted_before": deleted_before,
        },
    )

    return PPMonthlyUploadResponse(
        scope=s, year=year, month=month,
        filename=filename,
        rows_total=len(parsed.rows) + parsed.invalid,
        rows_matched=inserted,
        rows_unmatched=len(unmatched),
        rows_invalid=parsed.invalid,
        unmatched_codes=unmatched[:50],
        inserted=inserted,
        deleted_before=deleted_before,
    )


@router.delete("/monthly", status_code=status.HTTP_204_NO_CONTENT)
async def reset_monthly(
    scope: str = Query("adp"),
    year: int = Query(...),
    month: int = Query(...),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    s = _validate_scope(scope)
    _validate_year_month(year, month)
    deleted = await svc.reset_scope_monthly(
        session, tenant_id, s, year, month,
    )
    await audit_service.log_event(
        session,
        event_type="pret_productie.monthly_reset",
        tenant_id=tenant_id,
        user_id=current_user.id,
        target_type="pret_productie_monthly",
        target_id=tenant_id,
        metadata={"scope": s, "year": year, "month": month, "deleted": deleted},
    )
    return None
